"""Eval harness for the coaching assistant.

Case schema (one JSON object per line):
  question            what the user asks
  expect_refusal      true if the knowledge base should NOT cover it
  refusal_by          "gate" (default): the code-level relevance gate must refuse, checkable offline
                      "model": a real model must decline; only checkable with --live, skipped offline
  must_retrieve       doc stems that must appear in retrieval (retrieval quality)
  must_cite           true if the answer must carry at least one valid citation
  must_not_include    phrases that must not appear (fabrication tripwires)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from coaching_ai.assistant import REFUSAL_MARKER, CoachingAssistant


@dataclass
class CaseResult:
    question: str
    failures: list[str] = field(default_factory=list)
    skipped: bool = False

    @property
    def passed(self) -> bool:
        return not self.failures


def load_cases(path: str | Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def run_case(assistant: CoachingAssistant, case: dict, live: bool = False) -> CaseResult:
    result = CaseResult(case["question"])

    if case.get("expect_refusal") and case.get("refusal_by") == "model" and not live:
        result.skipped = True  # a stub model cannot demonstrate refusal behaviour
        return result

    answer = assistant.ask(case["question"])

    if case.get("expect_refusal"):
        declined = answer.refused or REFUSAL_MARKER in answer.text.lower()
        if not declined:
            result.failures.append("should have declined (out of scope) but answered")
        return result
    if answer.refused:
        result.failures.append("refused an in-scope question")
        return result

    docs = {r.split("#")[0] for r in answer.retrieved}
    for needed in case.get("must_retrieve", []):
        if needed not in docs:
            result.failures.append(f"retrieval missed '{needed}' (got {sorted(docs)})")
    if case.get("must_cite") and not answer.cited:
        result.failures.append("answer has no citations")
    if answer.invalid_citations:
        result.failures.append(f"cited ids that were not retrieved: {answer.invalid_citations}")
    lowered = answer.text.lower()
    for phrase in case.get("must_not_include", []):
        if phrase.lower() in lowered:
            result.failures.append(f"contains forbidden phrase '{phrase}'")
    return result


def run_suite(assistant: CoachingAssistant, cases: list[dict], live: bool = False) -> list[CaseResult]:
    return [run_case(assistant, c, live) for c in cases]


def pass_rate(results: list[CaseResult]) -> float:
    ran = [r for r in results if not r.skipped]
    return sum(r.passed for r in ran) / len(ran) if ran else 0.0


def summarize(results: list[CaseResult]) -> str:
    ran = [r for r in results if not r.skipped]
    skipped = len(results) - len(ran)
    lines = [f"{sum(r.passed for r in ran)}/{len(ran)} cases passed"
             + (f" ({skipped} live-only skipped; use --live)" if skipped else "")]
    for r in results:
        if not r.passed:
            lines.append(f"FAIL {r.question!r}")
            lines += [f"     - {f}" for f in r.failures]
    return "\n".join(lines)
