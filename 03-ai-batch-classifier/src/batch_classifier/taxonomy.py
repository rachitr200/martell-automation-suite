LABELS = {
    "purchase_intent": "Prospect signals they want to buy, book, or move forward.",
    "pricing_objection": "Prospect pushes back on price, value, or budget.",
    "support_issue": "Existing customer reports a problem, bug, billing or access issue.",
    "churn_risk": "Customer signals they may cancel, pause, or leave.",
    "general_question": "Informational question with no clear buying, support, or churn signal.",
}

SYSTEM_PROMPT = (
    "You classify one sales/support conversation into exactly one label.\n"
    "Labels:\n"
    + "\n".join(f"- {name}: {desc}" for name, desc in LABELS.items())
    + '\n\nRespond with JSON only: {"label": "<label>", "reason": "<max 15 words>"}'
)
