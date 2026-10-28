"""Property audit for the post-migration cleanup phase.

A CRM move (e.g. GoHighLevel -> HubSpot) usually leaves behind imported fields nobody uses,
near-duplicate fields created by different people, and legacy-prefixed names. Input comes from
a properties export plus fill rates (share of records with a value, 0..1).
"""

from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher

from hubspot_ops.common import Finding, sort_findings, to_date

SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
LEGACY_MARKERS = ("ghl", "gohighlevel", "highlevel")


def _norm(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()


def audit_properties(
    props: list[dict],
    fill_rates: dict[str, float],
    today: date,
    stale_days: int = 90,
    fill_threshold: float = 0.01,
    similarity: float = 0.88,
    legacy_markers: tuple[str, ...] = LEGACY_MARKERS,
) -> list[Finding]:
    findings: list[Finding] = []

    for p in props:
        name, label = p["name"], p.get("label", "")
        created = to_date(p.get("created_at"))
        old_enough = created is None or (today - created).days >= stale_days
        if fill_rates.get(name, 0.0) < fill_threshold and old_enough:
            findings.append(Finding(
                "medium", "unused", name,
                f"filled on {fill_rates.get(name, 0.0):.1%} of records and older than {stale_days} days",
            ))
        if not SNAKE.match(name):
            findings.append(Finding("low", "naming", name, "internal name is not lowercase snake_case"))
        text = f"{name} {label}".lower()
        if any(m in text for m in legacy_markers):
            findings.append(Finding("medium", "legacy", name, "looks like a leftover from the old CRM"))

    for i, a in enumerate(props):
        for b in props[i + 1:]:
            if _norm(a.get("label", "")) and (
                SequenceMatcher(None, _norm(a["label"]), _norm(b.get("label", ""))).ratio() >= similarity
            ):
                findings.append(Finding(
                    "medium", "duplicate", f"{a['name']} / {b['name']}",
                    f"labels '{a['label']}' and '{b['label']}' are nearly identical",
                ))
    return sort_findings(findings)
