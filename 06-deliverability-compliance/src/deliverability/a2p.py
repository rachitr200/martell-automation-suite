"""Pre-flight checks for a US A2P 10DLC campaign registration (Twilio / SalesMsg style).

Carriers reject campaigns for predictable reasons: vague descriptions, sample messages with no
brand name or opt-out language, no proof of consent, missing privacy/terms pages. This catches
those BEFORE submission, because a rejected campaign costs days and fees.

These are common review criteria, not a legal or carrier guarantee. Check Twilio's current
registration docs for the authoritative rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

USE_CASES = {
    "marketing", "account_notification", "customer_care", "delivery_notification",
    "2fa", "mixed", "low_volume", "polling_voting", "public_service_announcement",
}
OPT_OUT = re.compile(r"\b(stop|unsubscribe|opt[- ]?out)\b", re.IGNORECASE)
URL = re.compile(r"^https://[^\s/]+\.[^\s/]+", re.IGNORECASE)
SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly")


@dataclass(frozen=True)
class Issue:
    severity: str  # blocker | warning
    field: str
    message: str


def validate_campaign(c: dict) -> list[Issue]:
    issues: list[Issue] = []

    def block(field, msg):
        issues.append(Issue("blocker", field, msg))

    def warn(field, msg):
        issues.append(Issue("warning", field, msg))

    if c.get("use_case") not in USE_CASES:
        block("use_case", f"use_case must be one of {sorted(USE_CASES)}")
    if len((c.get("description") or "").strip()) < 40:
        block("description", "describe who you message, why, and what the messages contain (40+ characters)")

    flow = (c.get("message_flow") or "").strip()
    if len(flow) < 40:
        block("message_flow", "explain exactly how people opt in (40+ characters)")
    elif not re.search(r"\b(consent|opt[- ]?in|agree|check(?:box|ing)|text .* to)\b", flow, re.IGNORECASE):
        warn("message_flow", "does not clearly describe consent; reviewers look for an explicit opt-in step")

    for field in ("privacy_policy_url", "terms_url"):
        if not URL.match(c.get(field) or ""):
            block(field, "needs a public https:// URL")

    samples = c.get("sample_messages") or []
    if not 2 <= len(samples) <= 5:
        block("sample_messages", "provide between 2 and 5 sample messages")
    brand = (c.get("brand_name") or "").strip().lower()
    for i, msg in enumerate(samples, 1):
        if brand and brand not in msg.lower():
            warn(f"sample_messages[{i}]", "does not name the brand")
        if any(s in msg.lower() for s in SHORTENERS):
            block(f"sample_messages[{i}]", "public URL shorteners are commonly filtered; use your own domain")
    if c.get("use_case") in ("marketing", "mixed") and not any(OPT_OUT.search(m) for m in samples):
        block("sample_messages", "marketing samples need opt-out language such as 'Reply STOP to opt out'")

    if not c.get("opt_out_keywords_supported", False):
        block("opt_out_keywords_supported", "STOP handling must be supported")
    if not c.get("help_keyword_supported", False):
        warn("help_keyword_supported", "HELP keyword response is expected")
    if c.get("age_gated_or_restricted_content"):
        warn("age_gated_or_restricted_content", "restricted categories need extra disclosures and may be refused")
    return issues


def summarize(issues: list[Issue]) -> str:
    blockers = [i for i in issues if i.severity == "blocker"]
    lines = ["READY to submit" if not blockers else f"NOT READY: {len(blockers)} blocker(s)"]
    lines += [f"  [{i.severity}] {i.field}: {i.message}" for i in issues]
    return "\n".join(lines)
