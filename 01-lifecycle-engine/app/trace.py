"""Per-customer event timeline: answers 'what happened to this customer's data, in order?'"""

from __future__ import annotations


def customer_id_of(payload: dict) -> str | None:
    return ((payload.get("data") or {}).get("object") or {}).get("customer")


def build_trace(events: list[dict], customer_id: str) -> list[dict]:
    """events: dicts with id, type, created, status, attempts, last_error, payload."""
    mine = [e for e in events if customer_id_of(e["payload"]) == customer_id]
    mine.sort(key=lambda e: (e["created"], e["id"]))
    return [
        {
            "event_id": e["id"],
            "type": e["type"],
            "created": e["created"],
            "status": e["status"],
            "attempts": e["attempts"],
            "error": e.get("last_error"),
        }
        for e in mine
    ]
