import json
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[2] / "data" / "eval_set.jsonl"


def load_eval_set(path: Path = DEFAULT) -> tuple[list[dict], dict[str, str]]:
    conversations, gold = [], {}
    for line in Path(path).read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            gold[row["id"]] = row.pop("label")
            conversations.append(row)
    return conversations, gold
