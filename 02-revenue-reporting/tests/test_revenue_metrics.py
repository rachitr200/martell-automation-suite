from datetime import date

from revenue_report.cli import build_message
from revenue_report.metrics import (
    DailyReport,
    at_risk_customers,
    compute_daily_report,
    flags,
    monthly_cents,
    upcoming_renewals,
)

DAY = date(2026, 10, 28)


def sub(cid, amount=10000, interval="month", status="active", started="2026-01-01", **kw):
    return {"customer_id": cid, "plan": "pro", "amount_cents": amount, "interval": interval,
            "status": status, "started_at": started, **kw}


def test_annual_plans_are_normalised_to_monthly():
    assert monthly_cents(sub("a", 120000, "year")) == 10000


def test_mrr_new_and_churn():
    subs = [sub("a"), sub("b", started="2026-10-28"), sub("c", status="canceled", canceled_at="2026-10-28")]
    r = compute_daily_report(subs, [], DAY)
    assert r.mrr_cents == 20000          # a + b; c churned today
    assert r.prior_mrr_cents == 20000    # a + c
    assert r.new_mrr_cents == 10000 and r.new_customers == 1
    assert r.churned_mrr_cents == 10000 and r.churned_customers == 1
    assert r.net_new_mrr_cents == 0


def test_trials_do_not_count_as_revenue():
    r = compute_daily_report([sub("a", status="trialing")], [], DAY)
    assert r.mrr_cents == 0 and r.active_customers == 0


def test_collected_and_failed_payments():
    inv = [
        {"customer_id": "a", "amount_cents": 500, "status": "paid", "created": "2026-10-28"},
        {"customer_id": "b", "amount_cents": 700, "status": "failed", "created": "2026-10-28"},
        {"customer_id": "c", "amount_cents": 900, "status": "paid", "created": "2026-10-27"},
    ]
    r = compute_daily_report([], inv, DAY)
    assert r.collected_cents == 500
    assert (r.failed_count, r.failed_cents) == (1, 700)


def test_renewals_split_renewing_from_ending():
    subs = [
        sub("a", current_period_end="2026-11-02"),
        sub("b", current_period_end="2026-11-05", cancel_at_period_end=True),
        sub("c", current_period_end="2027-03-01"),  # outside window
    ]
    renewing, ending = upcoming_renewals(subs, DAY, within_days=14)
    assert [r["customer_id"] for r in renewing] == ["a"]
    assert [r["customer_id"] for r in ending] == ["b"]
    assert renewing[0]["days_left"] == 5


def test_at_risk_clears_once_a_later_payment_succeeds():
    failed = {"customer_id": "a", "amount_cents": 100, "status": "failed", "created": "2026-10-25"}
    paid_later = {"customer_id": "a", "amount_cents": 100, "status": "paid", "created": "2026-10-27"}
    assert [r["customer_id"] for r in at_risk_customers([failed], DAY)] == ["a"]
    assert at_risk_customers([failed, paid_later], DAY) == []


def test_old_failures_are_not_at_risk():
    old = {"customer_id": "a", "amount_cents": 100, "status": "failed", "created": "2026-09-01"}
    assert at_risk_customers([old], DAY) == []


def test_flags_mrr_drop_and_failure_spike():
    def rep(mrr, failed=0, new=0, churned=0):
        return DailyReport(DAY, mrr, 100000, 0, 0, 0, new, churned, 0, failed, 0)

    history = [rep(100000, failed=1) for _ in range(5)]
    out = flags(rep(90000, failed=6, new=0, churned=2), history)
    assert any("MRR fell" in f for f in out)
    assert any("Failed payments" in f for f in out)
    assert any("churned" in f for f in out)
    assert flags(rep(100000, failed=1), history) == []


def test_end_to_end_message_from_sample_shapes():
    subs = [sub("a", current_period_end="2026-11-02"), sub("b", started="2026-10-28")]
    text = build_message(subs, [], DAY, summarizer=lambda prompt: "Steady day.")
    assert "Daily revenue" in text and "Steady day." in text and "MRR $200" in text
