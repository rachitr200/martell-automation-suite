import base64

from deliverability import a2p
from deliverability.dns_auth import analyze_dkim, analyze_dmarc, analyze_spf, grade


def sev(check):
    return [s for s, _ in check.findings]


# ---- SPF ----
def test_spf_missing_and_duplicate_are_critical():
    assert sev(analyze_spf([])) == ["critical"]
    assert "critical" in sev(analyze_spf(["v=spf1 -all", "v=spf1 include:a.com -all"]))


def test_spf_plus_all_is_critical_and_question_all_is_high():
    assert "critical" in sev(analyze_spf(["v=spf1 include:a.com +all"]))
    assert "high" in sev(analyze_spf(["v=spf1 include:a.com ?all"]))
    assert "critical" in sev(analyze_spf(["v=spf1 include:a.com all"]))  # bare 'all' means +all


def test_spf_hard_fail_is_clean_and_softfail_is_low():
    assert analyze_spf(["v=spf1 include:_spf.google.com -all"]).findings == []
    assert sev(analyze_spf(["v=spf1 include:_spf.google.com ~all"])) == ["low"]


def test_spf_lookup_limit_counts_lookup_mechanisms_only():
    many = "v=spf1 " + " ".join(f"include:s{i}.com" for i in range(11)) + " -all"
    check = analyze_spf([many])
    assert check.details["top_level_lookups"] == 11 and "critical" in sev(check)
    ips = analyze_spf(["v=spf1 ip4:1.2.3.4 ip6:::1 -all"])
    assert ips.details["top_level_lookups"] == 0  # ip4/ip6 cost no lookups


# ---- DMARC ----
def test_dmarc_policy_progression():
    assert sev(analyze_dmarc([])) == ["high"]
    assert "medium" in sev(analyze_dmarc(["v=DMARC1; p=none; rua=mailto:r@x.com"]))
    assert analyze_dmarc(["v=DMARC1; p=reject; rua=mailto:r@x.com"]).findings == []
    assert "low" in sev(analyze_dmarc(["v=DMARC1; p=reject"]))  # no rua
    assert "low" in sev(analyze_dmarc(["v=DMARC1; p=quarantine; pct=25; rua=mailto:r@x.com"]))


# ---- DKIM ----
def key(n_bytes):
    return base64.b64encode(b"\x01" * n_bytes).decode()


def test_dkim_key_strength_estimates():
    assert analyze_dkim([f"v=DKIM1; k=rsa; p={key(294)}"]).details["approx_key_bits"] == 2048
    weak = analyze_dkim([f"v=DKIM1; k=rsa; p={key(162)}"])
    assert weak.details["approx_key_bits"] == 1024 and "medium" in sev(weak)


def test_dkim_revoked_invalid_missing_and_testing():
    assert sev(analyze_dkim([])) == ["critical"]
    assert "high" in sev(analyze_dkim(["v=DKIM1; k=rsa; p="]))
    assert "high" in sev(analyze_dkim(["v=DKIM1; k=rsa; p=%%%not-base64%%%"]))
    assert "medium" in sev(analyze_dkim([f"v=DKIM1; t=y; p={key(294)}"]))


def test_grade_reflects_worst_finding():
    assert grade([analyze_spf([])]) == "F"
    assert grade([analyze_dmarc([])]) == "D"
    good = [analyze_spf(["v=spf1 include:a.com -all"]), analyze_dmarc(["v=DMARC1; p=reject; rua=mailto:a@b.co"])]
    assert grade(good) == "A"


# ---- A2P 10DLC ----
def good_campaign(**over):
    c = {
        "brand_name": "Acme Coaching",
        "use_case": "marketing",
        "description": "Acme Coaching sends event reminders and offers to members who opted in on our site.",
        "message_flow": "Members check an unchecked consent box on our signup form agreeing to receive texts.",
        "privacy_policy_url": "https://acme.example/privacy",
        "terms_url": "https://acme.example/terms",
        "sample_messages": [
            "Acme Coaching: your workshop starts at 5pm. Reply STOP to opt out.",
            "Acme Coaching: new replay is live at https://acme.example/r. Reply STOP to opt out.",
        ],
        "opt_out_keywords_supported": True,
        "help_keyword_supported": True,
    }
    c.update(over)
    return c


def blockers(issues):
    return [i.field for i in issues if i.severity == "blocker"]


def test_a_complete_campaign_is_ready():
    assert blockers(a2p.validate_campaign(good_campaign())) == []
    assert a2p.summarize(a2p.validate_campaign(good_campaign())).startswith("READY")


def test_vague_description_and_missing_consent_block():
    out = a2p.validate_campaign(good_campaign(description="marketing texts", message_flow="web form"))
    assert {"description", "message_flow"} <= set(blockers(out))


def test_marketing_samples_without_opt_out_block():
    out = a2p.validate_campaign(good_campaign(sample_messages=["Acme Coaching: big sale today!", "Acme Coaching: last day!"]))
    assert "sample_messages" in blockers(out)


def test_url_shorteners_and_non_https_policy_urls_block():
    out = a2p.validate_campaign(good_campaign(
        privacy_policy_url="http://acme.example/privacy",
        sample_messages=["Acme Coaching: see https://bit.ly/x Reply STOP to opt out", "Acme Coaching: hi. STOP to opt out"],
    ))
    assert "privacy_policy_url" in blockers(out) and "sample_messages[1]" in blockers(out)


def test_sample_without_brand_name_is_a_warning_not_a_blocker():
    out = a2p.validate_campaign(good_campaign(sample_messages=["Your workshop starts at 5pm. Reply STOP to opt out.", "Acme Coaching: hi. Reply STOP to opt out."]))
    assert any(i.field == "sample_messages[1]" and i.severity == "warning" for i in out)
    assert blockers(out) == []
