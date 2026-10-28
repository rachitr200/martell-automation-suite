"""Live DNS fetch. Needs `pip install dnspython`; kept optional so the analysis core has no deps."""

from __future__ import annotations


def fetch_txt(name: str) -> list[str]:
    import dns.exception
    import dns.resolver

    try:
        answers = dns.resolver.resolve(name, "TXT")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout):
        return []
    return ["".join(part.decode() for part in rdata.strings) for rdata in answers]


def fetch_domain(domain: str, selectors: list[str]) -> dict:
    return {
        "spf": fetch_txt(domain),
        "dmarc": fetch_txt(f"_dmarc.{domain}"),
        "dkim": {s: fetch_txt(f"{s}._domainkey.{domain}") for s in selectors},
    }
