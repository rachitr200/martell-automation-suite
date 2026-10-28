"""Nightly reconciliation across the three systems of record.

Event-driven sync can still drift (a missed webhook, a manual edit in the CRM, a failed revoke).
This compares snapshots and reports the *seam* where each customer's data disagrees, ranked by
revenue and security impact. Pure function: fetching the snapshots is a separate concern.

stripe:  {customer_id: {email, status, plan}}
crm:     {customer_id: {subscription_status, subscription_plan}}
members: set of lowercase emails with access
"""

from __future__ import annotations

from dataclasses import dataclass

GRANTS_ACCESS = {"active", "trialing", "past_due"}  # past_due keeps access during dunning


@dataclass(frozen=True)
class Discrepancy:
    severity: str  # high | medium | low
    kind: str
    customer_id: str
    detail: str


_ORDER = {"high": 0, "medium": 1, "low": 2}


def reconcile(stripe: dict, crm: dict, members: set[str], grants_access: set[str] = GRANTS_ACCESS) -> list[Discrepancy]:
    out: list[Discrepancy] = []
    members = {m.lower() for m in members}
    known_emails = set()

    for cid, s in stripe.items():
        email = (s.get("email") or "").lower()
        known_emails.add(email)
        entitled = s["status"] in grants_access

        if entitled and email and email not in members:
            out.append(Discrepancy("high", "missing_access", cid, f"{s['status']} in Stripe but {email} has no access"))
        if not entitled and email in members:
            out.append(Discrepancy("high", "access_not_revoked", cid, f"{s['status']} in Stripe but {email} still has access"))

        contact = crm.get(cid)
        if contact is None:
            if entitled:
                out.append(Discrepancy("medium", "missing_in_crm", cid, "paying customer has no CRM contact"))
            continue
        if contact.get("subscription_status") != s["status"]:
            out.append(Discrepancy("medium", "crm_status_mismatch", cid,
                                   f"Stripe {s['status']} vs CRM {contact.get('subscription_status')}"))
        if entitled and contact.get("subscription_plan") != s.get("plan"):
            out.append(Discrepancy("low", "crm_plan_mismatch", cid,
                                   f"Stripe {s.get('plan')} vs CRM {contact.get('subscription_plan')}"))

    for email in sorted(members - known_emails):
        out.append(Discrepancy("medium", "orphan_access", "-", f"{email} has access but no Stripe customer"))
    return sorted(out, key=lambda d: (_ORDER[d.severity], d.kind, d.customer_id))
