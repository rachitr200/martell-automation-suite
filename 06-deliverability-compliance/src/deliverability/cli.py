"""
python -m deliverability.cli domain example.com --selector s1 --selector google   (needs dnspython)
python -m deliverability.cli records --spf "v=spf1 include:_spf.google.com ~all" --dmarc "v=DMARC1; p=none"
python -m deliverability.cli a2p campaign.json
"""

import argparse
import json

from deliverability import a2p, dns_auth


def _report(checks):
    for c in checks:
        print(f"{c.mechanism}: {'ok' if c.ok else 'PROBLEM'}")
        for sev, msg in c.findings:
            print(f"  [{sev}] {msg}")
    print(f"\nOverall grade: {dns_auth.grade(checks)}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("domain"); d.add_argument("domain"); d.add_argument("--selector", action="append", default=[])
    r = sub.add_parser("records")
    r.add_argument("--spf", action="append", default=[]); r.add_argument("--dmarc", action="append", default=[])
    r.add_argument("--dkim", action="append", default=[])
    a = sub.add_parser("a2p"); a.add_argument("campaign")
    args = p.parse_args(argv)

    if args.cmd == "a2p":
        print(a2p.summarize(a2p.validate_campaign(json.load(open(args.campaign)))))
        return
    if args.cmd == "domain":
        from deliverability.lookup import fetch_domain

        rec = fetch_domain(args.domain, args.selector)
        checks = [dns_auth.analyze_spf(rec["spf"]), dns_auth.analyze_dmarc(rec["dmarc"])]
        checks += [dns_auth.analyze_dkim(v) for v in rec["dkim"].values()]
    else:
        checks = [dns_auth.analyze_spf(args.spf), dns_auth.analyze_dmarc(args.dmarc)]
        if args.dkim:
            checks.append(dns_auth.analyze_dkim(args.dkim))
    _report(checks)


if __name__ == "__main__":
    main()
