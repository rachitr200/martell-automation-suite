from app.reconcile import reconcile
from app.trace import build_trace


def kinds(found):
    return [(d.kind, d.customer_id) for d in found]


def test_clean_state_has_no_discrepancies():
    stripe = {"c1": {"email": "A@x.com", "status": "active", "plan": "pro"}}
    crm = {"c1": {"subscription_status": "active", "subscription_plan": "pro"}}
    assert reconcile(stripe, crm, {"a@x.com"}) == []  # email case is normalised


def test_paying_customer_without_access_is_high_severity():
    stripe = {"c1": {"email": "a@x.com", "status": "active", "plan": "pro"}}
    out = reconcile(stripe, {"c1": {"subscription_status": "active", "subscription_plan": "pro"}}, set())
    assert kinds(out) == [("missing_access", "c1")] and out[0].severity == "high"


def test_canceled_customer_who_kept_access_is_a_revenue_leak():
    stripe = {"c1": {"email": "a@x.com", "status": "canceled", "plan": "pro"}}
    crm = {"c1": {"subscription_status": "canceled", "subscription_plan": "pro"}}
    assert kinds(reconcile(stripe, crm, {"a@x.com"})) == [("access_not_revoked", "c1")]


def test_past_due_keeps_access_during_dunning_by_default():
    stripe = {"c1": {"email": "a@x.com", "status": "past_due", "plan": "pro"}}
    crm = {"c1": {"subscription_status": "past_due", "subscription_plan": "pro"}}
    assert reconcile(stripe, crm, {"a@x.com"}) == []
    assert kinds(reconcile(stripe, crm, {"a@x.com"}, grants_access={"active"})) == [("access_not_revoked", "c1")]


def test_crm_drift_and_orphans_are_reported_and_ranked():
    stripe = {
        "c1": {"email": "a@x.com", "status": "active", "plan": "pro"},
        "c2": {"email": "b@x.com", "status": "active", "plan": "pro"},
    }
    crm = {"c1": {"subscription_status": "canceled", "subscription_plan": "basic"}}  # c2 missing entirely
    out = reconcile(stripe, crm, {"a@x.com", "b@x.com", "ghost@x.com"})
    assert ("crm_status_mismatch", "c1") in kinds(out)
    assert ("crm_plan_mismatch", "c1") in kinds(out)
    assert ("missing_in_crm", "c2") in kinds(out)
    assert ("orphan_access", "-") in kinds(out)
    assert [d.severity for d in out] == sorted((d.severity for d in out), key=["high", "medium", "low"].index)


def ev(i, typ, created, customer, status="processed"):
    return {"id": i, "type": typ, "created": created, "status": status, "attempts": 1,
            "payload": {"data": {"object": {"customer": customer}}}}


def test_trace_filters_to_one_customer_and_orders_by_stripe_time():
    events = [ev("e3", "invoice.paid", 300, "c1"), ev("e1", "checkout.session.completed", 100, "c1"),
              ev("x", "invoice.paid", 200, "c2"), ev("e2", "invoice.payment_failed", 200, "c1", status="failed")]
    trace = build_trace(events, "c1")
    assert [t["event_id"] for t in trace] == ["e1", "e2", "e3"]
    assert trace[1]["status"] == "failed"


def test_trace_tolerates_events_without_a_customer():
    events = [{"id": "e", "type": "ping", "created": 1, "status": "ignored", "attempts": 1, "payload": {}}]
    assert build_trace(events, "c1") == []
