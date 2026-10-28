from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from coaching_ai.kb import Chunk, Index

LLM = Callable[[str, str], str]  # (system, user) -> text
CITATION = re.compile(r"\[([a-z0-9_\-]+#\d+)\]")
REFUSAL_MARKER = "don't have a framework"
REFUSAL = (
    "I don't have a framework that covers that. I can help with the coaching material I've been "
    "given, so try asking about it in terms of time, delegation, hiring or pricing."
)


def build_system(chunks: list[Chunk]) -> str:
    context = "\n\n".join(f"[{c.id}] {c.text}" for c in chunks)
    return (
        "You are a business coaching assistant. Answer ONLY from the context below.\n"
        "Rules:\n"
        "1. Cite every claim with its id in square brackets, e.g. [example_doc#1].\n"
        "2. If the context does not answer the question, say you don't have a framework for it.\n"
        "3. Never invent frameworks, statistics, or quotes. Keep answers under 120 words.\n\n"
        f"CONTEXT:\n{context}"
    )


@dataclass
class Answer:
    text: str
    retrieved: list[str]
    cited: list[str] = field(default_factory=list)
    invalid_citations: list[str] = field(default_factory=list)
    refused: bool = False


class CoachingAssistant:
    def __init__(
        self, index: Index, llm: LLM, k: int = 3, min_score: float = 0.12, min_coverage: float = 0.3
    ):
        self.index, self.llm, self.k = index, llm, k
        self.min_score, self.min_coverage = min_score, min_coverage

    def ask(self, question: str) -> Answer:
        hits = [
            (c, s)
            for c, s in self.index.search(question, self.k)
            if s >= self.min_score and self.index.coverage(question, c) >= self.min_coverage
        ]
        if not hits:
            # Coarse guardrail in code: clearly unrelated questions never reach the LLM. Borderline
            # ones do, and rule 2 of the system prompt makes the model refuse; the live evals
            # check that behaviour.
            return Answer(REFUSAL, retrieved=[], refused=True)
        chunks = [c for c, _ in hits]
        text = self.llm(build_system(chunks), question)
        retrieved = [c.id for c in chunks]
        cited = list(dict.fromkeys(CITATION.findall(text)))
        return Answer(
            text,
            retrieved=retrieved,
            cited=cited,
            invalid_citations=[c for c in cited if c not in retrieved],
        )


def anthropic_llm(model: str | None = None) -> LLM:
    import anthropic

    client = anthropic.Anthropic()
    model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")

    def run(system: str, user: str) -> str:
        msg = client.messages.create(
            model=model, max_tokens=400, system=system, messages=[{"role": "user", "content": user}]
        )
        return msg.content[0].text

    return run
