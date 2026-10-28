"""Deterministic keyword classifier. It is the control group: any LLM approach has to beat it
on the eval set to justify its cost. 'Know when to use a deterministic script' made concrete."""

RULES = [
    ("churn_risk", ["cancel", "canceling", "cancelling", "pause my", "not using", "refund", "switch to"]),
    ("support_issue", ["can't log", "cannot log", "not working", "error", "charged twice", "locked out", "bug"]),
    ("pricing_objection", ["too expensive", "expensive", "price", "cost", "budget", "cheaper", "discount"]),
    ("purchase_intent", ["sign me up", "ready to", "book", "start today", "get started", "buy", "how do i join"]),
]


def classify_text(text: str) -> str:
    lowered = text.lower()
    for label, keywords in RULES:
        if any(k in lowered for k in keywords):
            return label
    return "general_question"


def classify_all(conversations: list[dict]) -> dict[str, str]:
    return {
        c["id"]: classify_text(" ".join(m["text"] for m in c["messages"] if m["role"] == "customer"))
        for c in conversations
    }
