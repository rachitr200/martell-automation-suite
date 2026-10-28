import json

from sqlalchemy import func, select

from app.models import Customer, CustomerStatus, EventStatus, StripeEvent
from app.processor import retry_failed
from tests.helpers import SECRET, checkout_completed, make_event, post_event, sign


def _event(session_factory, event_id):
    with session_factory() as s:
        return s.get(StripeEvent, event_id)


def _customer(session_factory, stripe_id="cus_1"):
    with session_factory() as s:
        return s.scalar(select(Customer).where(Customer.stripe_customer_id == stripe_id))


# --- request validation ----------------------------------------------------------------------


def test_bad_signature_rejected(client, session_factory):
    resp = post_event(client, checkout_completed(), secret="wrong_secret")
    assert resp.status_code == 400
    with session_factory() as s:
        assert s.scalar(select(func.count()).select_from(StripeEvent)) == 0


def test_stale_signature_timestamp_rejected(client):
    resp = post_event(client, checkout_completed(), signature_timestamp=1)
    assert resp.status_code == 400


def test_malformed_event_rejected(client):
    payload = json.dumps({"no": "id"}).encode()
    resp = client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": sign(payload), "content-type": "application/json"},
    )
    assert resp.status_code == 400


# --- happy path ------------------------------------------------------------------------------


def test_checkout_completed_creates_customer_and_grants_access(
    client, session_factory, integrations
):
    resp = post_event(client, checkout_completed())
    assert resp.status_code == 200
    assert resp.json() == {"status": "processed"}

    customer = _customer(session_factory)
    assert customer.email == "a@example.com"
    assert customer.plan == "pro"
    assert customer.status == CustomerStatus.ACTIVE
    assert integrations.access.granted == [("a@example.com", "pro")]
    assert integrations.crm.calls[-1]["status"] == "active"


def test_unhandled_event_type_is_ignored_not_failed(client, session_factory):
    resp = post_event(client, make_event("evt_x", "charge.refunded", 100, {"customer": "cus_1"}))
    assert resp.json() == {"status": "ignored"}
    assert _event(session_factory, "evt_x").status == EventStatus.IGNORED


# --- idempotency -----------------------------------------------------------------------------


def test_duplicate_event_is_acknowledged_but_processed_once(
    client, session_factory, integrations
):
    event = checkout_completed()
    first = post_event(client, event)
    second = post_event(client, event)

    assert first.json() == {"status": "processed"}
    assert second.status_code == 200
    assert second.json() == {"status": "duplicate"}
    assert len(integrations.access.granted) == 1
    with session_factory() as s:
        assert s.scalar(select(func.count()).select_from(StripeEvent)) == 1


# --- ordering --------------------------------------------------------------------------------


def test_out_of_order_event_does_not_resurrect_canceled_customer(
    client, session_factory, integrations
):
    post_event(client, checkout_completed(created=100))
    # The cancellation (created=300) arrives BEFORE an older update (created=200).
    post_event(client, make_event("evt_del", "customer.subscription.deleted", 300, {"customer": "cus_1"}))
    post_event(
        client,
        make_event(
            "evt_upd", "customer.subscription.updated", 200, {"customer": "cus_1", "status": "active"}
        ),
    )

    customer = _customer(session_factory)
    assert customer.status == CustomerStatus.CANCELED
    assert customer.last_event_created == 300
    assert integrations.access.revoked == ["a@example.com"]
    assert _event(session_factory, "evt_upd").status == EventStatus.PROCESSED  # dropped, not failed


def test_payment_failed_then_paid(client, session_factory):
    post_event(client, checkout_completed(created=100))
    post_event(client, make_event("evt_f", "invoice.payment_failed", 200, {"customer": "cus_1"}))
    assert _customer(session_factory).status == CustomerStatus.PAST_DUE
    post_event(client, make_event("evt_p", "invoice.paid", 300, {"customer": "cus_1"}))
    assert _customer(session_factory).status == CustomerStatus.ACTIVE


# --- failure handling ------------------------------------------------------------------------


def test_failure_is_recorded_and_state_rolled_back_then_retry_succeeds(
    client, session_factory, integrations, settings
):
    integrations.access.fail = True
    resp = post_event(client, checkout_completed())

    # Stripe still gets a 200: the event is stored and we own the retry.
    assert resp.status_code == 200
    assert resp.json() == {"status": "failed"}
    event = _event(session_factory, "evt_1")
    assert event.attempts == 1
    assert "access provider down" in event.last_error
    assert _customer(session_factory) is None  # handler's DB changes were rolled back

    integrations.access.fail = False
    with session_factory() as s:
        assert retry_failed(s, integrations, settings.max_attempts) == 1

    event = _event(session_factory, "evt_1")
    assert event.status == EventStatus.PROCESSED
    assert event.attempts == 2
    assert event.last_error is None
    assert _customer(session_factory).status == CustomerStatus.ACTIVE


def test_event_goes_dead_after_max_attempts(client, session_factory, integrations, settings):
    integrations.access.fail = True
    post_event(client, checkout_completed())  # attempt 1 (max_attempts is 3)

    with session_factory() as s:
        retry_failed(s, integrations, settings.max_attempts)  # attempt 2
    assert _event(session_factory, "evt_1").status == EventStatus.FAILED
    with session_factory() as s:
        retry_failed(s, integrations, settings.max_attempts)  # attempt 3
    assert _event(session_factory, "evt_1").status == EventStatus.DEAD

    with session_factory() as s:
        assert retry_failed(s, integrations, settings.max_attempts) == 0  # dead is not retried


# --- admin -----------------------------------------------------------------------------------


def test_admin_retry_disabled_without_token(client):
    assert client.post("/admin/retry").status_code == 503


def test_admin_retry_requires_matching_token(client, settings):
    settings.admin_token = "s3cret"
    assert client.post("/admin/retry", headers={"x-admin-token": "nope"}).status_code == 401
    ok = client.post("/admin/retry", headers={"x-admin-token": "s3cret"})
    assert ok.status_code == 200
    assert ok.json() == {"retried": 0}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


# --- trace ------------------------------------------------------------------------------------


def test_trace_requires_admin_token_and_returns_ordered_history(client, settings):
    post_event(client, checkout_completed(created=100))
    post_event(client, make_event("evt_f", "invoice.payment_failed", 200, {"customer": "cus_1"}))
    post_event(client, make_event("evt_other", "invoice.paid", 150, {"customer": "cus_2"}))

    assert client.get("/trace/cus_1").status_code == 503  # disabled until a token is configured
    settings.admin_token = "s3cret"
    assert client.get("/trace/cus_1", headers={"x-admin-token": "nope"}).status_code == 401

    body = client.get("/trace/cus_1", headers={"x-admin-token": "s3cret"}).json()
    assert [e["event_id"] for e in body["events"]] == ["evt_1", "evt_f"]  # cus_2's event excluded
    assert body["customer"]["status"] == "past_due"
