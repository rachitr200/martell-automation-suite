"""Tiny retrieval layer: markdown -> chunks -> TF-IDF cosine search. Standard library only.

Deliberately simple. The point is the surrounding system (citations, guardrails, evals), and
that you can swap this for embeddings or a vector store without touching anything else.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

TOKEN = re.compile(r"[a-z0-9']+")
STOP = frozenset(
    "a an and are as at be but by can do does for from has have how i if in into is it its me my "
    "of on or our should so that the their them then there these they this to us was we what when "
    "where which who why will with would you your".split()
)


def stem(token: str) -> str:
    """Very light stemmer (plurals, -ing, -ed, trailing e) so 'prices' matches 'pricing'."""
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            token = token[: -len(suffix)]
            break
    if token.endswith("e") and len(token) > 3:
        token = token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    return [stem(t) for t in TOKEN.findall(text.lower()) if t not in STOP and len(t) > 1]


@dataclass(frozen=True)
class Chunk:
    id: str  # "<doc>#<n>", the citation handle the model must use
    doc: str
    text: str


def load_dir(path: str | Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for file in sorted(Path(path).glob("*.md")):
        heading = ""
        n = 0
        for block in re.split(r"\n\s*\n", file.read_text()):
            block = block.strip()
            if not block:
                continue
            if block.startswith("<!--"):  # authoring notes are not knowledge
                continue
            if block.startswith("#"):
                heading = block.lstrip("# ").strip()
                continue
            n += 1
            text = f"{heading}: {block}" if heading else block
            chunks.append(Chunk(f"{file.stem}#{n}", file.stem, text))
    return chunks


class Index:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        docs = [Counter(tokenize(c.text)) for c in chunks]
        self.token_sets = [set(d) for d in docs]
        df: Counter = Counter()
        for d in docs:
            df.update(d.keys())
        n = len(chunks)
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}
        self.vectors = [self._weigh(d) for d in docs]

    def _weigh(self, counts: Counter) -> dict[str, float]:
        vec = {t: c * self.idf.get(t, 0.0) for t, c in counts.items() if t in self.idf}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def coverage(self, query: str, chunk: Chunk) -> float:
        """Share of the question's distinct terms that appear in the chunk (0..1).

        Cosine alone rewards a single shared generic word on a short query; coverage asks
        whether the chunk addresses what was actually asked.
        """
        terms = set(tokenize(query))
        if not terms:
            return 0.0
        return len(terms & self.token_sets[self.chunks.index(chunk)]) / len(terms)

    def search(self, query: str, k: int = 3) -> list[tuple[Chunk, float]]:
        q = self._weigh(Counter(tokenize(query)))
        scored = [
            (chunk, sum(w * vec.get(t, 0.0) for t, w in q.items()))
            for chunk, vec in zip(self.chunks, self.vectors, strict=True)
        ]
        scored = [s for s in scored if s[1] > 0]
        return sorted(scored, key=lambda s: (-s[1], s[0].id))[:k]
