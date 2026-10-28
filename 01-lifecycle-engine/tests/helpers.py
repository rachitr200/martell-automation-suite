import hashlib
import hmac
import json
import time

SECRET = "whsec_test"


def sign(payload: bytes, timestamp: int | None = None, secret: str = SECRET) -> str:
    ts = int(time.time()) if timestamp is None else timestamp
    digest = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def make_event(event_id: str, event_type: str, created: int, obj: dict) -> dict:
    return {
        "id": event_id,
        "object": "event",
        "type": event_type,
        "created": created,
        "data": {"object": obj},
    }


def checkout_completed(event_id="evt_1", created=100, customer="cus_1", email="a@example.com"):
    return make_event(
        event_id,
        "checkout.session.completed",
        created,
        {"customer": customer, "customer_details": {"email": email}, "metadata": {"plan": "pro"}},
    )


def post_event(client, event: dict, *, signature_timestamp: int | None = None, secret=SECRET):
    payload = json.dumps(event).encode()
    return client.post(
        "/webhooks/stripe",
        content=payload,
        headers={
            "stripe-signature": sign(payload, signature_timestamp, secret),
            "content-type": "application/json",
        },
    )
