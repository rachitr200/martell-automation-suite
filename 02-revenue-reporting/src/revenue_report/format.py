from __future__ import annotations

from datetime import date

from revenue_report.metrics import DailyReport


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) / 100:,.0f}"


def render(
    report: DailyReport,
    renewing: list[dict],
    ending: list[dict],
    at_risk: list[dict],
    flag_lines: list[str],
    summary: str | None = None,
) -> str:
    delta = report.mrr_cents - report.prior_mrr_cents
    lines = [
        f"*Daily revenue: {report.day:%a %b %d, %Y}*",
        f"MRR {money(report.mrr_cents)} ({'+' if delta >= 0 else ''}{money(delta)} vs yesterday)",
        f"New {money(report.new_mrr_cents)} ({report.new_customers})"
        f"  Churned {money(report.churned_mrr_cents)} ({report.churned_customers})"
        f"  Active customers {report.active_customers}",
        f"Collected {money(report.collected_cents)}"
        f"  Failed {report.failed_count} ({money(report.failed_cents)})",
    ]
    if summary:
        lines += ["", summary]
    if flag_lines:
        lines += ["", "*Watch:*"] + [f"- {f}" for f in flag_lines]
    if ending:
        lines += ["", f"*Set to cancel at period end ({len(ending)}), save list:*"]
        lines += [_renewal_line(r) for r in ending[:5]]
    if renewing:
        total = sum(r["amount_cents"] for r in renewing)
        lines += ["", f"*Renewing in 14 days:* {len(renewing)} worth {money(total)}"]
    if at_risk:
        lines += ["", f"*Failed payment, still unpaid ({len(at_risk)}):*"]
        lines += [
            f"- {r['customer_id']}: {money(r['amount_cents'])} since {_fmt(r['failed_on'])}"
            for r in at_risk[:5]
        ]
    return "\n".join(lines)


def _fmt(d: date) -> str:
    return f"{d:%b %d}"


def _renewal_line(r: dict) -> str:
    return f"- {r['customer_id']} ({r['plan']}) {money(r['amount_cents'])} on {_fmt(r['date'])}"
