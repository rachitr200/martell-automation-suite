"""Optional one-paragraph narrative. The numbers always come from metrics.py; the LLM only
describes them, so it can never change a figure."""

from __future__ import annotations

import os
from collections.abc import Callable

from revenue_report.format import money
from revenue_report.metrics import DailyReport

SYSTEM = (
    "You write a 2-sentence morning revenue summary for a CEO. Use ONLY the figures given. "
    "Do not add numbers, causes or advice that are not in the input."
)


def build_prompt(report: DailyReport, flag_lines: list[str]) -> str:
    return (
        f"Date {report.day}. MRR {money(report.mrr_cents)}, prior {money(report.prior_mrr_cents)}. "
        f"New {money(report.new_mrr_cents)}, churned {money(report.churned_mrr_cents)}. "
        f"Collected {money(report.collected_cents)}, failed payments {report.failed_count}. "
        f"Flags: {'; '.join(flag_lines) or 'none'}."
    )


def anthropic_summarizer(model: str | None = None) -> Callable[[str], str]:
    import anthropic  # imported lazily so the report works without the SDK

    client = anthropic.Anthropic()
    model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")

    def run(prompt: str) -> str:
        msg = client.messages.create(
            model=model,
            max_tokens=250,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    return run
