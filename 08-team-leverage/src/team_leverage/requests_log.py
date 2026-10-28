"""Turn the team's recurring questions into a ranked build list.

The job is not to be a help desk; it is to make each question happen once. Log every request
(date, requester, category, minutes spent). This ranks categories by total time and says what
kind of fix each deserves, so effort goes to the biggest recurring cost first.

CSV columns: date,requester,category,minutes
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Opportunity:
    category: str
    count: int
    total_minutes: int
    requesters: int
    action: str


def _action(count: int, requesters: int) -> str:
    if count >= 5 and requesters >= 2:
        return "build a self-serve tool or slash command"
    if count >= 3:
        return "write a how-to with a copy-paste example"
    if count == 2:
        return "add to the FAQ and watch for a third"
    return "one-off: just answer it"


def rank(csv_text: str) -> list[Opportunity]:
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for row in csv.DictReader(io.StringIO(csv_text)):
        by_cat[row["category"].strip().lower()].append(row)
    out = []
    for cat, rows in by_cat.items():
        who = {r["requester"].strip().lower() for r in rows}
        out.append(Opportunity(cat, len(rows), sum(int(r["minutes"]) for r in rows), len(who), _action(len(rows), len(who))))
    return sorted(out, key=lambda o: (-o.total_minutes, o.category))


def report(opps: list[Opportunity]) -> str:
    lines = [f"{'category':<24}{'asks':>5}{'people':>8}{'minutes':>9}  action"]
    lines += [f"{o.category:<24}{o.count:>5}{o.requesters:>8}{o.total_minutes:>9}  {o.action}" for o in opps]
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    print(report(rank(open(sys.argv[1]).read())))
