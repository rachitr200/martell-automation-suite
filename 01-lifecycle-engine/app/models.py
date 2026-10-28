import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def _values(enum_cls: type[enum.Enum]) -> list[str]:
    return [m.value for m in enum_cls]


class Base(DeclarativeBase):
    pass


class EventStatus(enum.StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    IGNORED = "ignored"  # valid event, type we don't act on
    FAILED = "failed"  # will be retried
    DEAD = "dead"  # out of attempts; needs a human


class CustomerStatus(enum.StrEnum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


class StripeEvent(Base):
    """Every webhook we accept, keyed by Stripe's event id.

    The primary key doubles as the idempotency guard: a replayed event hits the
    unique constraint and is acknowledged without being processed again.
    """

    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    type: Mapped[str] = mapped_column(String(100), index=True)
    created: Mapped[int] = mapped_column(Integer)  # Stripe's unix timestamp
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, native_enum=False, length=20, values_callable=_values),
        default=EventStatus.RECEIVED,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stripe_customer_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    plan: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[CustomerStatus] = mapped_column(
        Enum(CustomerStatus, native_enum=False, length=20, values_callable=_values),
        default=CustomerStatus.ACTIVE,
    )
    # Stripe `created` of the newest event applied; used to drop out-of-order events.
    last_event_created: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
