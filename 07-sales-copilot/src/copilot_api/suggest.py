"""Turn a live thread into reply suggestions grounded in the playbook.

Without an LLM it returns real replies that preceded won deals (deterministic, auditable).
With one it drafts in that style from those examples, with instructions not to invent facts.
"""

from __future__ import annotations

from collections.abc import Callable

from copilot_api.patterns import classify_objection

LLM = Callable[[str, str], str]  # (system, user) -> text

SYSTEM = (
    "You draft a short reply for a sales rep. Match the tone and structure of the winning examples. "
    "Never invent prices, discounts, guarantees, features, or deadlines that are not in the thread "
    "or examples. If the prospect needs information you do not have, ask one clarifying question. "
    "Maximum 60 words."
)


def last_prospect_message(thread: list[dict]) -> str | None:
    for m in reversed(thread):
        if m["role"] == "prospect":
            return m["text"]
    return None


def suggest_reply(playbook: dict, thread: list[dict], llm: LLM | None = None, max_examples: int = 3) -> dict:
    last = last_prospect_message(thread)
    if last is None:
        return {"objection": None, "suggestions": [], "note": "no prospect message in thread"}

    kind = classify_objection(last)
    examples = playbook.get("objection_replies", {}).get(kind or "", [])[:max_examples]
    if not examples:
        return {"objection": kind, "suggestions": [], "note": "no winning examples for this situation yet"}

    grounded = [
        {"source": "won_deal", "text": e["reply"], "conversation": e["conversation"]} for e in examples
    ]
    if llm is None:
        return {"objection": kind, "suggestions": grounded}

    shown = "\n\n".join(f"Prospect: {e['prospect']}\nWinning reply: {e['reply']}" for e in examples)
    convo = "\n".join(f"{m['role'].capitalize()}: {m['text']}" for m in thread[-6:])
    draft = llm(SYSTEM, f"WINNING EXAMPLES\n{shown}\n\nCURRENT THREAD\n{convo}\n\nDraft the next rep reply.")
    return {"objection": kind, "suggestions": [{"source": "ai_draft", "text": draft.strip()}] + grounded}
