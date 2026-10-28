"""Mine closed-won vs closed-lost conversations for what actually works.

conversation: {id, outcome: "won"|"lost", messages: [{role: "prospect"|"rep", text}]}

Two outputs, both grounded in real conversations rather than generic sales advice:
  - phrases reps use that are over-represented in WON deals (log-odds, with a support floor)
  - objection -> the rep replies that preceded a closed-won outcome
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

STOP = frozenset(
    "a an and are as at be but by can do for from have i if in is it me my of on or so that the "
    "this to we you your with will would just".split()
)

OBJECTIONS = {
    "price": ["expensive", "too much", "price", "cost", "budget", "afford", "cheaper"],
    "timing": ["not now", "not ready", "later", "next quarter", "next month", "bad time", "too busy"],
    "think_about_it": ["think about it", "think it over", "talk to my", "run it by", "discuss with"],
    "competitor": ["competitor", "already use", "currently use", "other tool", "alternative", "comparing"],
    "trust": ["does it work", "proof", "results", "guarantee", "case study", "not sure it"],
}


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def ngrams(text: str, sizes=(2, 3)) -> set[str]:
    words = tokens(text)
    out = set()
    for n in sizes:
        for i in range(len(words) - n + 1):
            gram = words[i : i + n]
            if all(w in STOP for w in gram):
                continue
            out.add(" ".join(gram))
    return out


def classify_objection(text: str) -> str | None:
    lowered = text.lower()
    for kind, keywords in OBJECTIONS.items():
        if any(k in lowered for k in keywords):
            return kind
    return None


def winning_phrases(convs: list[dict], min_support: int = 2, top: int = 10) -> list[dict]:
    """Phrases (counted once per conversation) with the highest won-vs-lost log-odds."""
    won_n = sum(c["outcome"] == "won" for c in convs)
    lost_n = sum(c["outcome"] == "lost" for c in convs)
    won, lost = Counter(), Counter()
    for c in convs:
        grams = set().union(*(ngrams(m["text"]) for m in c["messages"] if m["role"] == "rep")) if c["messages"] else set()
        (won if c["outcome"] == "won" else lost).update(grams)
    rows = []
    for gram, w in won.items():
        if w < min_support:
            continue
        l = lost.get(gram, 0)
        lift = math.log((w + 1) / (won_n + 2)) - math.log((l + 1) / (lost_n + 2))
        rows.append({"phrase": gram, "won": w, "lost": l, "lift": round(lift, 3)})
    rows.sort(key=lambda r: (-r["lift"], -r["won"], r["phrase"]))
    return rows[:top]


def objection_replies(convs: list[dict]) -> dict[str, list[dict]]:
    """For each objection type: how reps replied in conversations that were then WON."""
    out: dict[str, list[dict]] = defaultdict(list)
    for c in convs:
        if c["outcome"] != "won":
            continue
        msgs = c["messages"]
        for i, m in enumerate(msgs[:-1]):
            kind = classify_objection(m["text"]) if m["role"] == "prospect" else None
            if kind and msgs[i + 1]["role"] == "rep":
                out[kind].append({"conversation": c["id"], "prospect": m["text"], "reply": msgs[i + 1]["text"]})
    return dict(out)


def build_playbook(convs: list[dict]) -> dict:
    return {
        "stats": {"won": sum(c["outcome"] == "won" for c in convs), "lost": sum(c["outcome"] == "lost" for c in convs)},
        "top_phrases": winning_phrases(convs),
        "objection_replies": objection_replies(convs),
    }
