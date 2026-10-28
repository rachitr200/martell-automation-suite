from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class EvalReport:
    accuracy: float
    total: int
    per_label: dict[str, dict[str, float]]
    confusion: dict[tuple[str, str], int]
    misses: list[tuple[str, str, str]] = field(default_factory=list)  # (id, gold, predicted)


def evaluate(predictions: dict[str, str], gold: dict[str, str]) -> EvalReport:
    """Score predictions against gold labels. A missing prediction counts as wrong."""
    confusion: Counter = Counter()
    misses = []
    for cid, truth in gold.items():
        guess = predictions.get(cid, "missing")
        confusion[(truth, guess)] += 1
        if guess != truth:
            misses.append((cid, truth, guess))

    labels = sorted(set(gold.values()))
    per_label = {}
    for label in labels:
        tp = confusion[(label, label)]
        fp = sum(n for (t, g), n in confusion.items() if g == label and t != label)
        fn = sum(n for (t, g), n in confusion.items() if t == label and g != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {"precision": precision, "recall": recall, "f1": f1}

    total = len(gold)
    return EvalReport(
        accuracy=(total - len(misses)) / total if total else 0.0,
        total=total,
        per_label=per_label,
        confusion=dict(confusion),
        misses=sorted(misses),
    )


def format_report(report: EvalReport, title: str = "Eval") -> str:
    lines = [f"{title}: accuracy {report.accuracy:.0%} over {report.total}"]
    for label, m in report.per_label.items():
        lines.append(f"  {label:<18} P {m['precision']:.2f}  R {m['recall']:.2f}  F1 {m['f1']:.2f}")
    if report.misses:
        lines.append("  misses (id: gold -> predicted):")
        lines += [f"    {cid}: {g} -> {p}" for cid, g, p in report.misses]
    return "\n".join(lines)
