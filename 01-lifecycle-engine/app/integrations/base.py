"""Seams for the outside world.

Handlers only talk to these interfaces. Real HubSpot / community-platform clients plug in here
without touching event-processing logic. Implementations MUST be idempotent: a handler can run
more than once for the same event (a crash after the side effect but before commit, then retry).
"""

import logging
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger(__name__)


class CRM(Protocol):
    def upsert_contact(
        self, *, stripe_customer_id: str, email: str | None, plan: str | None, status: str
    ) -> None: ...


class AccessProvider(Protocol):
    def grant(self, *, email: str, plan: str | None) -> None: ...

    def revoke(self, *, email: str) -> None: ...


class NoopCRM:
    def upsert_contact(
        self, *, stripe_customer_id: str, email: str | None, plan: str | None, status: str
    ) -> None:
        log.info("crm.upsert_contact %s plan=%s status=%s", stripe_customer_id, plan, status)


class NoopAccess:
    def grant(self, *, email: str, plan: str | None) -> None:
        log.info("access.grant %s plan=%s", email, plan)

    def revoke(self, *, email: str) -> None:
        log.info("access.revoke %s", email)


@dataclass
class Integrations:
    crm: CRM
    access: AccessProvider
