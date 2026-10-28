from app.integrations.hubspot import HubSpotCRM, HubSpotError
from app.integrations.rest_access import AccessError, RestAccessProvider


class FakeTransport:
    """Records requests and replies from a queue of (status, body)."""

    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, method, url, body, headers):
        self.calls.append((method, url, body, headers))
        return self.responses.pop(0)


def crm(*responses):
    t = FakeTransport(*responses)
    return HubSpotCRM("tok", transport=t), t


UPSERT = dict(stripe_customer_id="cus_1", email="a@x.com", plan="pro", status="active")


def test_creates_contact_when_none_exists():
    client, t = crm((200, {"results": []}), (201, {"id": "1"}))
    client.upsert_contact(**UPSERT)
    assert [c[0] for c in t.calls] == ["POST", "POST"]
    assert t.calls[0][1].endswith("/crm/v3/objects/contacts/search")
    props = t.calls[1][2]["properties"]
    assert props == {"email": "a@x.com", "stripe_customer_id": "cus_1", "subscription_plan": "pro", "subscription_status": "active"}


def test_updates_existing_contact_by_id_without_resending_email():
    client, t = crm((200, {"results": [{"id": "42"}]}), (200, {}))
    client.upsert_contact(**UPSERT)
    method, url, body, _ = t.calls[1]
    assert (method, url.endswith("/contacts/42")) == ("PATCH", True)
    assert "email" not in body["properties"]


def test_conflict_on_create_falls_back_to_update():
    client, t = crm((200, {"results": []}), (409, {"message": "exists"}), (200, {"results": [{"id": "7"}]}), (200, {}))
    client.upsert_contact(**UPSERT)
    assert t.calls[-1][0] == "PATCH" and t.calls[-1][1].endswith("/contacts/7")


def test_api_errors_raise_so_the_event_is_retried():
    client, _ = crm((429, {"message": "rate limited"}))
    try:
        client.upsert_contact(**UPSERT)
    except HubSpotError as err:
        assert err.status == 429
        return
    raise AssertionError("expected HubSpotError")


def test_no_email_means_no_calls():
    client, t = crm()
    client.upsert_contact(stripe_customer_id="cus_1", email=None, plan="pro", status="active")
    assert t.calls == []


def test_bearer_token_is_sent():
    client, t = crm((200, {"results": []}), (201, {}))
    client.upsert_contact(**UPSERT)
    assert t.calls[0][3]["Authorization"] == "Bearer tok"


def access(*responses):
    t = FakeTransport(*responses)
    return RestAccessProvider("https://community.example/api/", "tok", transport=t), t


def test_grant_is_idempotent_when_already_a_member():
    provider, t = access((409, {}))
    provider.grant(email="a@x.com", plan="pro")  # must not raise
    assert t.calls[0][1] == "https://community.example/api/members"


def test_revoke_is_idempotent_when_already_gone_and_escapes_email():
    provider, t = access((404, {}))
    provider.revoke(email="a+b@x.com")
    assert t.calls[0][1].endswith("/members/a%2Bb%40x.com")


def test_server_errors_raise():
    for call in ("grant", "revoke"):
        provider, _ = access((500, {}))
        try:
            getattr(provider, call)(email="a@x.com", **({"plan": "pro"} if call == "grant" else {}))
        except AccessError as err:
            assert err.status == 500
            continue
        raise AssertionError(f"{call} should raise on 500")
