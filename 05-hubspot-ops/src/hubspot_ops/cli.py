"""
python -m hubspot_ops.cli properties --props props.json --fill fill.json
python -m hubspot_ops.cli marketing  --contacts contacts.json --tier-size 5000 --cost-per-tier 800
python -m hubspot_ops.cli workflows  --workflows workflows.json
Everything is read-only analysis of exports; nothing writes to HubSpot.
"""

import argparse
import json
from datetime import date

from hubspot_ops.marketing import recommend_non_marketing, tier_math, to_csv
from hubspot_ops.properties import audit_properties
from hubspot_ops.workflows import lint_workflows


def _print(findings):
    for f in findings:
        print(f"[{f.severity:<6}] {f.kind:<14} {f.subject}: {f.detail}")
    print(f"\n{len(findings)} findings")


def main(argv=None) -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("properties"); a.add_argument("--props", required=True); a.add_argument("--fill", required=True)
    b = sub.add_parser("marketing"); b.add_argument("--contacts", required=True)
    b.add_argument("--tier-size", type=int, required=True); b.add_argument("--cost-per-tier", type=float, required=True)
    b.add_argument("--inactive-days", type=int, default=180); b.add_argument("--csv-out")
    c = sub.add_parser("workflows"); c.add_argument("--workflows", required=True)
    args = p.parse_args(argv)
    today = date.today()

    if args.cmd == "properties":
        _print(audit_properties(json.load(open(args.props)), json.load(open(args.fill)), today))
    elif args.cmd == "workflows":
        _print(lint_workflows(json.load(open(args.workflows)), today))
    else:
        contacts = json.load(open(args.contacts))
        recs = recommend_non_marketing(contacts, today, args.inactive_days)
        m = tier_math(contacts, recs, args.tier_size, args.cost_per_tier)
        print(f"Marketing contacts: {m.marketing_now} -> {m.marketing_after}")
        print(f"Tiers: {m.tiers_before} -> {m.tiers_after}  (estimated monthly savings {m.monthly_savings:,.0f})")
        print(f"{len(recs)} contacts recommended for non-marketing (review before applying)")
        if args.csv_out:
            open(args.csv_out, "w").write(to_csv(recs))
            print(f"wrote {args.csv_out}")


if __name__ == "__main__":
    main()
