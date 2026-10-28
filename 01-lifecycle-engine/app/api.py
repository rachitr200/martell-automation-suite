import hmac
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.deps import get_integrations, raw_body
from app.integrations import Integrations
from app.models import Customer, StripeEvent
from app.processor import retry_failed, run_event
from app.stripe_verify import SignatureError, verify_signature
from app.trace import build_trace

router = APIRouter()


# Sync endpoint on purpose: FastAPI runs it in a threadpool, so blocking DB calls don't stall
# the event loop. The async dependency reads the raw body.
@router.post("/webhooks/stripe")
def stripe_webhook(
    request: Request,
    payload: bytes = Depends(raw_body),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    integrations: Integrations = Depends(get_integrations),
) -> dict:
    if not settings.stripe_webhook_secret:
        raise HTTPException(500, "Webhook secret not configured")

    try:
        verify_signature(
            payload,
            request.headers.get("stripe-signature", ""),
            settings.stripe_webhook_secret,
            settings.signature_tolerance_seconds,
        )
    except SignatureError as exc:
        raise HTTPException(400, str(exc)) from exc

    try:
        body = json.loads(payload)
        event = StripeEvent(
            id=body["id"], type=body["type"], created=body["created"], payload=body
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(400, "Malformed event") from exc

    session.add(event)
    try:
        session.commit()
    except IntegrityError:
        # Already stored: Stripe is retrying or replaying. Acknowledge, do nothing.
        session.rollback()
        return {"status": "duplicate"}

    # Always 200 once the event is durably stored. Processing failures are tracked on the
    # event row and retried by us, so Stripe's own retry schedule doesn't add duplicate noise.
    status = run_event(session, body["id"], integrations, settings.max_attempts)
    return {"status": status.value}


def _require_admin(token: str, settings: Settings) -> None:
    if not settings.admin_token:
        raise HTTPException(503, "Admin endpoints disabled")
    if not hmac.compare_digest(token, settings.admin_token):
        raise HTTPException(401, "Invalid admin token")


@router.post("/admin/retry")
def admin_retry(
    x_admin_token: str = Header(default=""),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    integrations: Integrations = Depends(get_integrations),
) -> dict:
    _require_admin(x_admin_token, settings)
    return {"retried": retry_failed(session, integrations, settings.max_attempts)}


@router.get("/trace/{stripe_customer_id}")
def trace_customer(
    stripe_customer_id: str,
    x_admin_token: str = Header(default=""),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Current state plus the ordered event history for one customer. Admin-only: it is PII."""
    _require_admin(x_admin_token, settings)
    customer = session.scalar(select(Customer).where(Customer.stripe_customer_id == stripe_customer_id))
    rows = session.scalars(select(StripeEvent).order_by(StripeEvent.created)).all()
    events = [
        {"id": e.id, "type": e.type, "created": e.created, "status": e.status.value,
         "attempts": e.attempts, "last_error": e.last_error, "payload": e.payload}
        for e in rows
    ]
    return {
        "customer": None if customer is None else {
            "stripe_customer_id": customer.stripe_customer_id, "email": customer.email,
            "plan": customer.plan, "status": customer.status.value,
            "last_event_created": customer.last_event_created,
        },
        "events": build_trace(events, stripe_customer_id),
    }
