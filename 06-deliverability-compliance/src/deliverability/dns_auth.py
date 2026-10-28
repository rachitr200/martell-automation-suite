"""SPF / DKIM / DMARC record analysis. Input is the TXT record text, so the logic is offline,
deterministic and testable. `lookup.py` fetches live records when dnspython is installed."""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass, field

SPF_LOOKUP_MECHANISMS = {"include", "a", "mx", "ptr", "exists", "redirect"}
SPF_LOOKUP_LIMIT = 10


@dataclass
class Check:
    mechanism: str
    findings: list[tuple[str, str]] = field(default_factory=list)  # (severity, message)
    details: dict = field(default_factory=dict)

    def add(self, severity: str, message: str) -> None:
        self.findings.append((severity, message))

    @property
    def ok(self) -> bool:
        return not any(sev in ("critical", "high") for sev, _ in self.findings)


def _tags(record: str) -> dict[str, str]:
    out = {}
    for part in record.split(";"):
        key, _, value = part.strip().partition("=")
        if key:
            out[key.strip().lower()] = value.strip()
    return out


def analyze_spf(txt_records: list[str]) -> Check:
    check = Check("SPF")
    spf = [r for r in txt_records if r.strip().lower().startswith("v=spf1")]
    if not spf:
        check.add("critical", "no SPF record found")
        return check
    if len(spf) > 1:
        check.add("critical", "multiple SPF records: receivers treat this as a permanent error")
    terms = spf[0].split()[1:]

    all_terms = [t for t in terms if re.fullmatch(r"[+\-~?]?all", t.lower())]
    if not all_terms:
        check.add("medium", "no 'all' mechanism: unlisted senders are neither allowed nor rejected")
    else:
        qualifier = all_terms[-1][0] if all_terms[-1][0] in "+-~?" else "+"
        check.details["all"] = qualifier + "all"
        if qualifier == "+":
            check.add("critical", "'+all' authorises every server on the internet to send as you")
        elif qualifier == "?":
            check.add("high", "'?all' is neutral, so SPF gives receivers no signal")
        elif qualifier == "~":
            check.add("low", "'~all' (softfail) is acceptable while rolling out; '-all' once confident")

    lookups = sum(
        1 for t in terms if re.split(r"[:/=]", t.lstrip("+-~?"))[0].lower() in SPF_LOOKUP_MECHANISMS
    )
    check.details["top_level_lookups"] = lookups
    if lookups > SPF_LOOKUP_LIMIT:
        check.add("critical", f"{lookups} DNS lookups at the top level; the SPF limit is {SPF_LOOKUP_LIMIT}")
    elif lookups >= 8:
        check.add("medium", f"{lookups} top-level lookups; nested includes also count toward the limit of {SPF_LOOKUP_LIMIT}")
    if any(t.lstrip("+-~?").lower().startswith("ptr") for t in terms):
        check.add("medium", "'ptr' is deprecated and slow; remove it")
    return check


def analyze_dmarc(txt_records: list[str]) -> Check:
    check = Check("DMARC")
    found = [r for r in txt_records if r.strip().lower().startswith("v=dmarc1")]
    if not found:
        check.add("high", "no DMARC record at _dmarc.<domain>")
        return check
    tags = _tags(found[0])
    policy = tags.get("p", "").lower()
    check.details.update(policy=policy, pct=tags.get("pct", "100"))
    if policy == "none":
        check.add("medium", "p=none only monitors; move to quarantine, then reject, once reports look clean")
    elif policy not in ("quarantine", "reject"):
        check.add("high", f"invalid or missing policy tag p={policy!r}")
    if not tags.get("rua"):
        check.add("low", "no rua= address: you will not receive aggregate reports")
    try:
        if int(tags.get("pct", "100")) < 100:
            check.add("low", f"pct={tags['pct']} applies the policy to only part of your mail")
    except ValueError:
        check.add("medium", f"pct={tags.get('pct')!r} is not a number")
    return check


def analyze_dkim(txt_records: list[str]) -> Check:
    check = Check("DKIM")
    found = [r for r in txt_records if "p=" in r.lower()]
    if not found:
        check.add("critical", "no DKIM key found at <selector>._domainkey.<domain>")
        return check
    tags = _tags(found[0])
    key = re.sub(r"\s+", "", tags.get("p", ""))
    if not key:
        check.add("high", "empty p= means this DKIM key has been revoked")
        return check
    try:
        der = base64.b64decode(key, validate=True)
    except (binascii.Error, ValueError):
        check.add("high", "p= is not valid base64")
        return check
    # An RSA public key in DER is ~162 bytes at 1024 bits and ~294 bytes at 2048 bits.
    bits = 2048 if len(der) >= 270 else 1024 if len(der) >= 140 else 512
    check.details["approx_key_bits"] = bits
    if bits < 1024:
        check.add("high", "key looks shorter than 1024 bits")
    elif bits == 1024:
        check.add("medium", "1024-bit key; rotate to 2048-bit")
    if tags.get("t", "").lower() == "y":
        check.add("medium", "t=y marks DKIM as testing mode; receivers may ignore failures")
    return check


def grade(checks: list[Check]) -> str:
    severities = [sev for c in checks for sev, _ in c.findings]
    if "critical" in severities:
        return "F"
    if "high" in severities:
        return "D"
    if "medium" in severities:
        return "B"
    return "A" if not severities else "A-"
