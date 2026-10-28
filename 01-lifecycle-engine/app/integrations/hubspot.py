"""HubSpot CRM v3 contact sync.

Upserts a contact keyed by email and writes the subscription fields. The custom properties
below must exist in HubSpot first (Settings > Properties); HubSpot rejects unknown ones.
"""

from __future__ import annotations

from urllib.parse import quote

from app.integrations.http import Transport, urllib_transport

PROP_CUSTOMER_ID = "stripe_customer_id"
PROP_PLAN = "subscription_plan"
PROP_STATUS = "subscription_status"


class HubSpotError(RuntimeError):
    def __init__(self, status: int, body: dict):
        super().__init__(f"HubSpot API returned {status}: {body.get('message', body)}")
        self.status = status


class HubSpotCRM:
    def __init__(self, token: str, transport: Transport = urllib_transport, base: str = "https://api.hubapi.com"):
        self.base, self.transport = base, transport
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        return self.transport(method, f"{self.base}{path}", body, self.headers)

    def _find_id(self, email: str) -> str | None:
        status, data = self._call("POST", "/crm/v3/objects/contacts/search", {
            "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}],
            "properties": ["email"],
            "limit": 1,
        })
        if status >= 400:
            raise HubSpotError(status, data)
        results = data.get("results", [])
        return results[0]["id"] if results else None

    def _patch(self, contact_id: str, props: dict) -> None:
        status, data = self._call("PATCH", f"/crm/v3/objects/contacts/{quote(contact_id)}", {"properties": props})
        if status >= 400:
            raise HubSpotError(status, data)

    def upsert_contact(self, *, stripe_customer_id: str, email: str | None, plan: str | None, status: str) -> None:
        if not email:
            return  # no stable key to match on; the caller still records the event
        props = {PROP_CUSTOMER_ID: stripe_customer_id, PROP_PLAN: plan or "", PROP_STATUS: status}

        existing = self._find_id(email)
        if existing:
            return self._patch(existing, props)

        code, data = self._call("POST", "/crm/v3/objects/contacts", {"properties": {"email": email, **props}})
        if code == 409:  # created by a concurrent event between our search and create
            existing = self._find_id(email)
            if existing:
                return self._patch(existing, props)
        if code >= 400:
            raise HubSpotError(code, data)
