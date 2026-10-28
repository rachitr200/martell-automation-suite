"""Daily revenue metrics from subscription and invoice snapshots.

Pure functions over plain dicts so the numbers are easy to test and to explain:

subscription: {customer_id, plan, amount_cents, interval ("month"|"year"), quantity?,
               status, started_at, canceled_at?, current_period_end?, cancel_at_period_end?}
invoice:      {customer_id, amount_cents, status ("paid"|"failed"|"open"), created}
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, timedelta

NON_REVENUE_STATUSES = {"trialing", "incomplete", "incomplete_expired"}


def to_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def monthly_cents(sub: dict) -> int:
    """Normalise a subscription to monthly recurring revenue in cents."""
    amount = int(sub["amount_cents"]) * int(sub.get("quantity", 1))
    return round(amount / 12) if sub.get("interval") == "year" else amount


def _counts(sub: dict) -> bool:
    return sub.get("status") not in NON_REVENUE_STATUSES


def _active_on(sub: dict, day: date) -> bool:
    started, canceled = to_date(sub["started_at"]), to_date(sub.get("canceled_at"))
    return started <= day and (canceled is None or canceled > day)


@dataclass
class DailyReport:
    day: date
    mrr_cents: int
    prior_mrr_cents: int
    new_mrr_cents: int
    churned_mrr_cents: int
    active_customers: int
    new_customers: int
    churned_customers: int
    collected_cents: int
    failed_count: int
    failed_cents: int

    @property
    def net_new_mrr_cents(self) -> int:
        return self.new_mrr_cents - self.churned_mrr_cents


def compute_daily_report(subs: list[dict], invoices: list[dict], day: date) -> DailyReport:
    revenue_subs = [s for s in subs if _counts(s)]
    now = [s for s in revenue_subs if _active_on(s, day)]
    before = [s for s in revenue_subs if _active_on(s, day - timedelta(days=1))]
    new = [s for s in revenue_subs if to_date(s["started_at"]) == day]
    churned = [s for s in revenue_subs if to_date(s.get("canceled_at")) == day]
    todays = [i for i in invoices if to_date(i["created"]) == day]
    failed = [i for i in todays if i["status"] == "failed"]
    return DailyReport(
        day=day,
        mrr_cents=sum(map(monthly_cents, now)),
        prior_mrr_cents=sum(map(monthly_cents, before)),
        new_mrr_cents=sum(map(monthly_cents, new)),
        churned_mrr_cents=sum(map(monthly_cents, churned)),
        active_customers=len({s["customer_id"] for s in now}),
        new_customers=len({s["customer_id"] for s in new}),
        churned_customers=len({s["customer_id"] for s in churned}),
        collected_cents=sum(int(i["amount_cents"]) for i in todays if i["status"] == "paid"),
        failed_count=len(failed),
        failed_cents=sum(int(i["amount_cents"]) for i in failed),
    )


def upcoming_renewals(subs: list[dict], today: date, within_days: int = 14):
    """Split active subscriptions renewing soon into (renewing, ending).

    `ending` are ones set to cancel at period end: the renewal-save list.
    """
    horizon = today + timedelta(days=within_days)
    renewing, ending = [], []
    for s in subs:
        if not _counts(s) or to_date(s.get("canceled_at")) is not None:
            continue
        end = to_date(s.get("current_period_end"))
        if end is None or not (today <= end <= horizon):
            continue
        row = {
            "customer_id": s["customer_id"],
            "plan": s.get("plan"),
            "amount_cents": int(s["amount_cents"]) * int(s.get("quantity", 1)),
            "date": end,
            "days_left": (end - today).days,
        }
        (ending if s.get("cancel_at_period_end") else renewing).append(row)
    key = lambda r: (r["date"], r["customer_id"])  # noqa: E731
    return sorted(renewing, key=key), sorted(ending, key=key)


def at_risk_customers(invoices: list[dict], today: date, window_days: int = 7) -> list[dict]:
    """Customers with a recent failed invoice that has not been followed by a paid one."""
    by_customer: dict[str, dict] = {}
    for inv in invoices:
        created = to_date(inv["created"])
        if created > today:
            continue
        row = by_customer.setdefault(inv["customer_id"], {"failed": None, "paid": None, "amt": 0})
        if inv["status"] == "failed" and (row["failed"] is None or created >= row["failed"]):
            row["failed"], row["amt"] = created, int(inv["amount_cents"])
        if inv["status"] == "paid" and (row["paid"] is None or created > row["paid"]):
            row["paid"] = created
    out = []
    for cid, row in by_customer.items():
        failed, paid = row["failed"], row["paid"]
        if failed and (today - failed).days <= window_days and (paid is None or paid < failed):
            out.append({"customer_id": cid, "failed_on": failed, "amount_cents": row["amt"]})
    return sorted(out, key=lambda r: (r["failed_on"], r["customer_id"]))


def flags(report: DailyReport, history: list[DailyReport]) -> list[str]:
    """Plain-language anomaly flags so the CEO's morning read says what changed, not just numbers."""
    out: list[str] = []
    if report.prior_mrr_cents and report.mrr_cents < report.prior_mrr_cents * 0.98:
        drop = 1 - report.mrr_cents / report.prior_mrr_cents
        out.append(f"MRR fell {drop:.1%} day over day")
    past = [h.failed_count for h in history]
    if report.failed_count and len(past) >= 3:
        mean, spread = statistics.mean(past), statistics.pstdev(past)
        if report.failed_count > mean + max(2 * spread, 1):
            out.append(
                f"Failed payments ({report.failed_count}) well above the recent average ({mean:.1f})"
            )
    if report.churned_customers and report.churned_customers > report.new_customers:
        out.append("More customers churned than joined today")
    return out
