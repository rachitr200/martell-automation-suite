from datetime import date

from hubspot_ops.marketing import recommend_non_marketing, tier_math, to_csv
from hubspot_ops.properties import audit_properties
from hubspot_ops.workflows import lint_workflows

TODAY = date(2026, 10, 28)


def kinds(findings, kind):
    return [f for f in findings if f.kind == kind]


def test_unused_property_needs_to_be_both_empty_and_old():
    props = [
        {"name": "old_empty", "label": "Old Empty", "created_at": "2025-01-01"},
        {"name": "new_empty", "label": "New Empty", "created_at": "2026-10-20"},
        {"name": "old_used", "label": "Old Used", "created_at": "2025-01-01"},
    ]
    found = kinds(audit_properties(props, {"old_used": 0.5}, TODAY), "unused")
    assert [f.subject for f in found] == ["old_empty"]  # new_empty is too young to judge


def test_duplicate_labels_and_naming_and_legacy_are_flagged():
    props = [
        {"name": "lead_source", "label": "Lead Source", "created_at": "2025-01-01"},
        {"name": "leadSource", "label": "Lead source", "created_at": "2025-01-01"},
        {"name": "ghl_stage", "label": "GHL Stage", "created_at": "2025-01-01"},
    ]
    fills = {"lead_source": 1, "leadSource": 1, "ghl_stage": 1}
    out = audit_properties(props, fills, TODAY)
    assert kinds(out, "duplicate")[0].subject == "lead_source / leadSource"
    assert [f.subject for f in kinds(out, "naming")] == ["leadSource"]
    assert [f.subject for f in kinds(out, "legacy")] == ["ghl_stage"]


def test_distinct_labels_are_not_called_duplicates():
    props = [{"name": "a", "label": "Plan Tier"}, {"name": "b", "label": "Stripe Customer ID"}]
    assert kinds(audit_properties(props, {"a": 1, "b": 1}, TODAY), "duplicate") == []


def contacts():
    base = {"marketing_status": "marketing", "lifecycle": "lead"}
    return [
        {"id": "1", "email": "recent@x.com", "last_engaged": "2026-10-01", **base},
        {"id": "2", "email": "stale@x.com", "last_engaged": "2025-09-01", **base},
        {"id": "3", "email": "never@x.com", **base},
        {"id": "4", "email": "unsub@x.com", "unsubscribed": True, "last_engaged": "2026-10-10", **base},
        {"id": "5", "email": "cust@x.com", "lifecycle": "customer", "marketing_status": "marketing"},
        {"id": "6", "email": "deal@x.com", "open_deal": True, "last_engaged": "2024-01-01", **base},
        {"id": "7", "email": "non@x.com", "marketing_status": "non-marketing", "lifecycle": "lead"},
    ]


def test_recommendations_protect_customers_and_open_deals():
    recs = recommend_non_marketing(contacts(), TODAY)
    assert sorted(r.contact_id for r in recs) == ["2", "3", "4"]  # never 1 (recent), 5 (customer), 6 (deal)


def test_tier_math_uses_supplied_tier_size_and_price():
    cs = contacts()
    recs = recommend_non_marketing(cs, TODAY)
    m = tier_math(cs, recs, tier_size=3, cost_per_tier=100)
    assert (m.marketing_now, m.marketing_after) == (6, 3)
    assert (m.tiers_before, m.tiers_after, m.monthly_savings) == (2, 1, 100)


def test_csv_export_has_header_and_rows():
    out = to_csv(recommend_non_marketing(contacts(), TODAY)).splitlines()
    assert out[0] == "contact_id,email,reason" and len(out) == 4


def test_workflow_lint_catches_dormant_junk_duplicates_and_missing_docs():
    wfs = [
        {"id": 1, "name": "Onboarding", "enabled": True, "description": "ok", "last_enrolled_at": "2026-10-27"},
        {"id": 2, "name": "Copy of Onboarding", "enabled": True, "last_enrolled_at": "2026-01-02"},
        {"id": 3, "name": "Renewal reminder", "enabled": True, "description": "x", "last_enrolled_at": "2026-10-20"},
        {"id": 4, "name": "renewal  reminder", "enabled": False},
    ]
    out = lint_workflows(wfs, TODAY)
    by_kind = {k: [f.subject for f in out if f.kind == k] for k in {f.kind for f in out}}
    assert by_kind["dormant"] == ["2 Copy of Onboarding"]
    assert by_kind["junk_name"] == ["2 Copy of Onboarding"]
    assert by_kind["undocumented"] == ["2 Copy of Onboarding"]
    assert by_kind["duplicate_name"] == ["4 renewal  reminder"]
    assert out[0].severity == "high"  # most urgent first
