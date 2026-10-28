"""python -m revenue_report.cli --subs subs.json --invoices invoices.json --date 2026-10-28"""

import argparse
import json
import os
from datetime import date, timedelta

from revenue_report import slack, summarize
from revenue_report.format import render
from revenue_report.metrics import (
    at_risk_customers,
    compute_daily_report,
    flags,
    to_date,
    upcoming_renewals,
)


def build_message(subs, invoices, day: date, summarizer=None) -> str:
    report = compute_daily_report(subs, invoices, day)
    history = [compute_daily_report(subs, invoices, day - timedelta(days=n)) for n in range(1, 8)]
    flag_lines = flags(report, history)
    renewing, ending = upcoming_renewals(subs, day)
    at_risk = at_risk_customers(invoices, day)
    summary = summarizer(summarize.build_prompt(report, flag_lines)) if summarizer else None
    return render(report, renewing, ending, at_risk, flag_lines, summary)


def main(argv=None) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--subs", required=True)
    p.add_argument("--invoices", required=True)
    p.add_argument("--date", default=None, help="YYYY-MM-DD, default today")
    p.add_argument("--summarize", action="store_true", help="add an LLM-written summary")
    p.add_argument("--post", action="store_true", help="post to SLACK_WEBHOOK_URL")
    args = p.parse_args(argv)

    subs = json.load(open(args.subs))
    invoices = json.load(open(args.invoices))
    day = to_date(args.date) or date.today()
    summarizer = summarize.anthropic_summarizer() if args.summarize else None
    text = build_message(subs, invoices, day, summarizer)
    print(text)
    if args.post:
        slack.post(os.environ["SLACK_WEBHOOK_URL"], text)


if __name__ == "__main__":
    main()
