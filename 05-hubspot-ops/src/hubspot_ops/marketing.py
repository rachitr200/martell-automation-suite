"""Marketing-contact tier optimisation.

HubSpot bills marketing contacts in tiers, so contacts that are marketing-eligible but will
never be marketed to are wasted spend. This finds candidates to set to non-marketing.

It only RECOMMENDS. It does not call HubSpot. Apply the output through a HubSpot list plus the
bulk action or a workflow, after a human reviews it. Tier size and price vary by contract, so
they are inputs, not assumptions.
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass
from datetime import date

from hubspot_ops.common import to_date

PROTECTED_LIFECYCLES = {"customer", "opportunity", "salesqualifiedlead"}


@dataclass(frozen=True)
class Recommendation:
    contact_id: str
    email: str
    reason: str


@dataclass(frozen=True)
class TierMath:
    marketing_now: int
    marketing_after: int
    tiers_before: int
    tiers_after: int
    monthly_savings: float


def recommend_non_marketing(
    contacts: list[dict], today: date, inactive_days: int = 180
) -> list[Recommendation]:
    """contact: {id, email, marketing_status, lifecycle, last_engaged?, unsubscribed?, open_deal?}"""
    out = []
    for c in contacts:
        if c.get("marketing_status") != "marketing":
            continue
        if c.get("lifecycle") in PROTECTED_LIFECYCLES or c.get("open_deal"):
            continue  # never touch people sales or support are actively working
        if c.get("unsubscribed"):
            out.append(Recommendation(c["id"], c["email"], "unsubscribed from email"))
            continue
        last = to_date(c.get("last_engaged"))
        if last is None:
            out.append(Recommendation(c["id"], c["email"], "never engaged with marketing"))
        elif (today - last).days >= inactive_days:
            out.append(Recommendation(c["id"], c["email"], f"no engagement in {(today - last).days} days"))
    return out


def tier_math(contacts: list[dict], recs: list[Recommendation], tier_size: int, cost_per_tier: float) -> TierMath:
    now = sum(1 for c in contacts if c.get("marketing_status") == "marketing")
    after = now - len(recs)
    before_tiers = math.ceil(now / tier_size) if now else 0
    after_tiers = math.ceil(after / tier_size) if after > 0 else 0
    return TierMath(now, after, before_tiers, after_tiers, (before_tiers - after_tiers) * cost_per_tier)


def to_csv(recs: list[Recommendation]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["contact_id", "email", "reason"])
    writer.writerows((r.contact_id, r.email, r.reason) for r in recs)
    return buf.getvalue()
