"""
python -m batch_classifier.cli baseline                 # offline: score the keyword baseline
python -m batch_classifier.cli llm --model <model>      # submit the eval set as one batch, then score
"""

import argparse
import os

from batch_classifier import baseline
from batch_classifier.data import load_eval_set
from batch_classifier.evals import evaluate, format_report


def main(argv=None) -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("baseline")
    llm = sub.add_parser("llm")
    llm.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5"))
    args = p.parse_args(argv)

    conversations, gold = load_eval_set()
    if args.cmd == "baseline":
        print(format_report(evaluate(baseline.classify_all(conversations), gold), "Keyword baseline"))
        return

    from batch_classifier.backend import AnthropicBackend
    from batch_classifier.runner import classify

    preds = classify(conversations, AnthropicBackend(), args.model)
    print(format_report(evaluate({k: v.label for k, v in preds.items()}, gold), f"LLM {args.model}"))


if __name__ == "__main__":
    main()
