"""Generic REST access provider (grant/revoke membership in a community platform).

Written against an assumed interface: POST {base}/members to add, DELETE {base}/members/{email}
to remove. Map the paths and payloads to the real platform's API (e.g. Mighty Networks) before
use. Both calls are idempotent: "already a member" and "already gone" count as success.
"""

from __future__ import annotations

from urllib.parse import quote

from app.integrations.http import Transport, urllib_transport


class AccessError(RuntimeError):
    def __init__(self, action: str, status: int):
        super().__init__(f"access provider {action} failed with HTTP {status}")
        self.status = status


class RestAccessProvider:
    def __init__(self, base: str, token: str, transport: Transport = urllib_transport):
        self.base = base.rstrip("/")
        self.transport = transport
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def grant(self, *, email: str, plan: str | None) -> None:
        status, _ = self.transport("POST", f"{self.base}/members", {"email": email, "plan": plan}, self.headers)
        if status not in (200, 201, 409):  # 409: already a member
            raise AccessError("grant", status)

    def revoke(self, *, email: str) -> None:
        status, _ = self.transport("DELETE", f"{self.base}/members/{quote(email)}", None, self.headers)
        if status not in (200, 202, 204, 404):  # 404: already gone
            raise AccessError("revoke", status)
