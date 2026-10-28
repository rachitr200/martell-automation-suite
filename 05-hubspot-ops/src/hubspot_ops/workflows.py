"""Workflow inventory lint: find dead, undocumented, duplicated, or test workflows."""

from __future__ import annotations

import re
from datetime import date

from hubspot_ops.common import Finding, sort_findings, to_date

JUNK_NAME = re.compile(r"\b(copy of|test|old|temp|do not use|deprecated)\b", re.IGNORECASE)


def lint_workflows(workflows: list[dict], today: date, dormant_days: int = 90) -> list[Finding]:
    """workflow: {id, name, enabled, description?, last_enrolled_at?}"""
    findings: list[Finding] = []
    seen: dict[str, str] = {}
    for w in workflows:
        wid, name = str(w["id"]), w.get("name", "")
        last = to_date(w.get("last_enrolled_at"))
        if w.get("enabled") and (last is None or (today - last).days >= dormant_days):
            findings.append(Finding("high", "dormant", f"{wid} {name}",
                                    f"enabled but no enrollments in {dormant_days}+ days"))
        if w.get("enabled") and not (w.get("description") or "").strip():
            findings.append(Finding("low", "undocumented", f"{wid} {name}", "enabled with no description"))
        if JUNK_NAME.search(name):
            findings.append(Finding("medium", "junk_name", f"{wid} {name}", "name suggests a copy, test, or retired workflow"))
        key = re.sub(r"\W+", " ", name.lower()).strip()
        if key in seen:
            findings.append(Finding("medium", "duplicate_name", f"{wid} {name}", f"same name as workflow {seen[key]}"))
        else:
            seen[key] = wid
    return sort_findings(findings)
