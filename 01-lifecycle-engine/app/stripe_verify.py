"""Stripe webhook signature verification (the `Stripe-Signature` header scheme).

Header looks like `t=1700000000,v1=<hex hmac>[,v1=<hex hmac>...]`. The signed payload is
`"{t}.{raw body}"`, HMAC-SHA256 with the endpoint secret. Implemented with the stdlib so it is
easy to test and has no SDK dependency.
"""

import hashlib
import hmac
import time


class SignatureError(Exception):
    pass


def verify_signature(
    payload: bytes,
    header: str,
    secret: str,
    tolerance_seconds: int = 300,
    now: float | None = None,
) -> None:
    if not secret:
        raise ValueError("Stripe webhook secret is not configured")

    parts: dict[str, list[str]] = {}
    for item in header.split(","):
        key, _, value = item.partition("=")
        parts.setdefault(key.strip(), []).append(value.strip())

    try:
        timestamp = int(parts["t"][0])
    except (KeyError, IndexError, ValueError):
        raise SignatureError("Malformed Stripe-Signature header") from None

    signatures = parts.get("v1", [])
    if not signatures:
        raise SignatureError("No v1 signature in header")

    signed = f"{timestamp}.".encode() + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, sig) for sig in signatures):
        raise SignatureError("Signature mismatch")

    if tolerance_seconds and abs((now if now is not None else time.time()) - timestamp) > (
        tolerance_seconds
    ):
        raise SignatureError("Timestamp outside tolerance")
