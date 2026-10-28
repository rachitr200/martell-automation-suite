"""Build Batch API requests and parse results. No network, no SDK: pure data transforms."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from batch_classifier.taxonomy import LABELS, SYSTEM_PROMPT

CUSTOM_ID = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")  # the Batch API's custom_id constraint


@dataclass
class Prediction:
    label: str
    reason: str = ""
    status: str = "succeeded"  # succeeded | errored | expired | canceled


def render(conversation: dict) -> str:
    return "\n".join(f"{m['role'].capitalize()}: {m['text']}" for m in conversation["messages"])


def build_requests(
    conversations: list[dict], model: str, max_tokens: int = 150, system: str = SYSTEM_PROMPT
) -> list[dict]:
    requests = []
    for conv in conversations:
        if not CUSTOM_ID.match(conv["id"]):
            raise ValueError(f"invalid custom_id {conv['id']!r}: use 1-64 letters, digits, _ or -")
        requests.append(
            {
                "custom_id": conv["id"],
                "params": {
                    "model": model,
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": render(conv)}],
                },
            }
        )
    return requests


def parse_label(text: str) -> tuple[str, str]:
    """Pull {"label","reason"} out of model text; tolerate code fences and chatter."""
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            label = str(data.get("label", "")).strip()
            if label in LABELS:
                return label, str(data.get("reason", ""))
        except json.JSONDecodeError:
            pass
    return "unparseable", text[:80]


def parse_results(entries) -> dict[str, Prediction]:
    """entries: dicts shaped like the Batch API results JSONL, one per request."""
    out: dict[str, Prediction] = {}
    for entry in entries:
        cid, result = entry["custom_id"], entry["result"]
        kind = result["type"]
        if kind != "succeeded":
            out[cid] = Prediction("error", str(result.get("error", "")), kind)
            continue
        blocks = result["message"]["content"]
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        label, reason = parse_label(text)
        out[cid] = Prediction(label, reason)
    return out
