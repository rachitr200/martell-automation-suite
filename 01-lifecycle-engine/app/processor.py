"""Event processing: dispatch, state transitions, failure and retry bookkeeping."""

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations import Integrations
from app.models import Customer, CustomerStatus, EventStatus, StripeEvent, utcnow

Handler = Callable[[Session, StripeEvent, Integrations], None]

_SUBSCRIPTION_STATUS = {
    "active": CustomerStatus.ACTIVE,
    "trialing": CustomerStatus.ACTIVE,
    "past_due": CustomerStatus.PAST_DUE,
    "unpaid": CustomerStatus.PAST_DUE,
    "canceled": CustomerStatus.CANCELED,
    "incomplete_expired": CustomerStatus.CANCELED,
}


# --- helpers ---------------------------------------------------------------------------------


def _object(event: StripeEvent) -> dict:
    return event.payload["data"]["object"]


def _customer_for(session: Session, stripe_customer_id: str | None) -> Customer:
    if not stripe_customer_id:
        raise ValueError("event object has no customer id")
    customer = session.scalar(
        select(Customer).where(Customer.stripe_customer_id == stripe_customer_id).with_for_update()
    )
    if customer is None:
        customer = Customer(stripe_customer_id=stripe_customer_id, last_event_created=0)
        session.add(customer)
        session.flush()
    return customer


def _is_stale(customer: Customer, event: StripeEvent) -> bool:
    """True if a newer event for this customer was already applied.

    Stripe does not guarantee delivery order. Strict `<` so two events sharing a timestamp
    are both applied.
    """
    return event.created < customer.last_event_created or (
        event.created == customer.last_event_created
        and customer.status == CustomerStatus.CANCELED
        and event.type != "customer.subscription.deleted"
    )


def _mark_applied(customer: Customer, event: StripeEvent) -> None:
    customer.last_event_created = max(customer.last_event_created, event.created)


def _sync_crm(customer: Customer, integrations: Integrations) -> None:
    integrations.crm.upsert_contact(
        stripe_customer_id=customer.stripe_customer_id,
        email=customer.email,
        plan=customer.plan,
        status=customer.status.value,
    )


# --- handlers --------------------------------------------------------------------------------


def on_checkout_completed(session: Session, event: StripeEvent, integrations: Integrations) -> None:
    obj = _object(event)
    if obj.get("payment_status") not in (None, "paid", "no_payment_required"):
        return  # delayed payment is not a paid entitlement
    customer = _customer_for(session, obj.get("customer"))
    email = (obj.get("customer_details") or {}).get("email") or obj.get("customer_email")
    if _is_stale(customer, event):
        # Hydrate identity from late checkout without overwriting newer entitlement state.
        customer.email = email or customer.email
        customer.plan = customer.plan or (obj.get("metadata") or {}).get("plan") or "member"
        _sync_crm(customer, integrations)
        if customer.status == CustomerStatus.ACTIVE and customer.email:
            integrations.access.grant(email=customer.email, plan=customer.plan)
        return
    customer.email = email or customer.email
    customer.plan = (obj.get("metadata") or {}).get("plan") or customer.plan or "member"
    customer.status = CustomerStatus.ACTIVE
    _mark_applied(customer, event)

    if not customer.email:
        raise ValueError(f"no email for customer {customer.stripe_customer_id}; cannot grant access")
    _sync_crm(customer, integrations)
    integrations.access.grant(email=customer.email, plan=customer.plan)


def on_invoice_paid(session: Session, event: StripeEvent, integrations: Integrations) -> None:
    customer = _customer_for(session, _object(event).get("customer"))
    if _is_stale(customer, event):
        return
    customer.status = CustomerStatus.ACTIVE
    _mark_applied(customer, event)
    _sync_crm(customer, integrations)


def on_payment_failed(session: Session, event: StripeEvent, integrations: Integrations) -> None:
    customer = _customer_for(session, _object(event).get("customer"))
    if _is_stale(customer, event):
        return
    customer.status = CustomerStatus.PAST_DUE
    _mark_applied(customer, event)
    _sync_crm(customer, integrations)


def on_subscription_updated(
    session: Session, event: StripeEvent, integrations: Integrations
) -> None:
    obj = _object(event)
    customer = _customer_for(session, obj.get("customer"))
    if _is_stale(customer, event):
        return

    previous_plan = customer.plan
    previous_status = customer.status
    new_status = _SUBSCRIPTION_STATUS.get(obj.get("status", ""))
    if new_status is not None:
        customer.status = new_status
    new_plan = (obj.get("metadata") or {}).get("plan")
    if new_plan:
        customer.plan = new_plan
    _mark_applied(customer, event)

    _sync_crm(customer, integrations)
    plan_changed = bool(new_plan) and new_plan != previous_plan
    if customer.status == CustomerStatus.CANCELED and customer.email:
        integrations.access.revoke(email=customer.email)
    if (plan_changed or previous_status != CustomerStatus.ACTIVE) and customer.status == CustomerStatus.ACTIVE and customer.email:
        integrations.access.grant(email=customer.email, plan=customer.plan)


def on_subscription_deleted(
    session: Session, event: StripeEvent, integrations: Integrations
) -> None:
    customer = _customer_for(session, _object(event).get("customer"))
    if _is_stale(customer, event):
        return
    customer.status = CustomerStatus.CANCELED
    _mark_applied(customer, event)
    _sync_crm(customer, integrations)
    if customer.email:
        integrations.access.revoke(email=customer.email)


HANDLERS: dict[str, Handler] = {
    "checkout.session.completed": on_checkout_completed,
    "invoice.paid": on_invoice_paid,
    "invoice.payment_failed": on_payment_failed,
    "customer.subscription.updated": on_subscription_updated,
    "customer.subscription.deleted": on_subscription_deleted,
}


# --- orchestration ---------------------------------------------------------------------------


def process_event(session: Session, event: StripeEvent, integrations: Integrations) -> EventStatus:
    handler = HANDLERS.get(event.type)
    if handler is None:
        return EventStatus.IGNORED
    handler(session, event, integrations)
    return EventStatus.PROCESSED


def run_event(
    session: Session, event_id: str, integrations: Integrations, max_attempts: int
) -> EventStatus:
    """Process one stored event and record the outcome.

    On success, the business-state changes and the event's `processed` status commit together.
    On failure, everything the handler did to the database is rolled back, then the failure is
    recorded on the event (FAILED to be retried, DEAD once attempts run out).
    """
    event = session.get(StripeEvent, event_id, with_for_update=True)
    if event is None:
        raise LookupError(f"unknown event {event_id}")
    if event.status in (EventStatus.PROCESSED, EventStatus.IGNORED, EventStatus.DEAD):
        return event.status
    attempts = event.attempts + 1

    try:
        status = process_event(session, event, integrations)
        event.attempts = attempts
        event.status = status
        event.last_error = None
        event.processed_at = utcnow()
        session.commit()
    except Exception as exc:
        session.rollback()
        event = session.get(StripeEvent, event_id)
        event.attempts = attempts
        event.last_error = f"{type(exc).__name__}: {exc}"[:2000]
        event.status = EventStatus.DEAD if attempts >= max_attempts else EventStatus.FAILED
        session.commit()

    return event.status


def retry_failed(
    session: Session, integrations: Integrations, max_attempts: int, limit: int = 100
) -> int:
    """Re-run FAILED events oldest-first (by Stripe's timestamp). Returns how many were tried."""
    ids = session.scalars(
        select(StripeEvent.id)
        .where(StripeEvent.status.in_([EventStatus.FAILED, EventStatus.RECEIVED]))
        .order_by(StripeEvent.created)
        .limit(limit)
    ).all()
    for event_id in ids:
        run_event(session, event_id, integrations, max_attempts)
    return len(ids)
