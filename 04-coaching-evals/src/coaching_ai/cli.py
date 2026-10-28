"""
python -m coaching_ai.cli evals --live         # run the eval suite against a real model; exit 1 under threshold
python -m coaching_ai.cli ask "How do I decide what to delegate?" --live
Without --live a stub model is used, which checks retrieval, citations and refusals only.
"""

import argparse
import sys
from pathlib import Path

from coaching_ai.assistant import CoachingAssistant, anthropic_llm
from coaching_ai.evals import load_cases, pass_rate, run_suite, summarize
from coaching_ai.kb import Index, load_dir

ROOT = Path(__file__).resolve().parents[2]


def stub_llm(system: str, user: str) -> str:
    first = system.split("CONTEXT:\n", 1)[1].split("\n\n", 1)[0]
    return f"From the notes: {first}"


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["ask", "evals"])
    p.add_argument("question", nargs="?")
    p.add_argument("--live", action="store_true")
    p.add_argument("--threshold", type=float, default=0.9)
    args = p.parse_args(argv)

    index = Index(load_dir(ROOT / "knowledge"))
    assistant = CoachingAssistant(index, anthropic_llm() if args.live else stub_llm)

    if args.cmd == "ask":
        ans = assistant.ask(args.question or "")
        print(ans.text, "\n\nretrieved:", ans.retrieved, "cited:", ans.cited)
        return 0

    results = run_suite(assistant, load_cases(ROOT / "evals" / "cases.jsonl"), live=args.live)
    print(summarize(results))
    return 0 if pass_rate(results) >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
