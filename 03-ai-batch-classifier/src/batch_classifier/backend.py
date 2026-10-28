"""Where batches actually run. The pipeline only depends on the BatchBackend interface, so
tests use FakeBackend and production uses AnthropicBackend."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol


class BatchBackend(Protocol):
    def submit(self, requests: list[dict]) -> str: ...

    def status(self, batch_id: str) -> str:  # "in_progress" | "ended" | ...
        ...

    def results(self, batch_id: str) -> Iterable[dict]: ...


class FakeBackend:
    """Deterministic stand-in: `responder(request) -> model text`."""

    def __init__(self, responder: Callable[[dict], str], polls_until_done: int = 1):
        self.responder, self._polls = responder, polls_until_done
        self.batches: dict[str, list[dict]] = {}
        self.status_calls = 0

    def submit(self, requests: list[dict]) -> str:
        batch_id = f"batch_{len(self.batches) + 1}"
        self.batches[batch_id] = requests
        return batch_id

    def status(self, batch_id: str) -> str:
        self.status_calls += 1
        return "ended" if self.status_calls > self._polls else "in_progress"

    def results(self, batch_id: str) -> Iterable[dict]:
        for req in self.batches[batch_id]:
            text = self.responder(req)
            yield {
                "custom_id": req["custom_id"],
                "result": {"type": "succeeded", "message": {"content": [{"type": "text", "text": text}]}},
            }


class AnthropicBackend:
    """Thin wrapper over client.messages.batches (Message Batches API).

    Batches are processed asynchronously at a discount versus synchronous calls, which suits
    bulk, non-urgent work like classifying a backlog of conversations. Not exercised against the
    live API in this repo's tests; run a 3-conversation batch first when you wire real keys.
    """

    def __init__(self, client=None):
        if client is None:
            import anthropic  # lazy: the rest of the package works without the SDK

            client = anthropic.Anthropic()
        self.client = client

    def submit(self, requests: list[dict]) -> str:
        return self.client.messages.batches.create(requests=requests).id

    def status(self, batch_id: str) -> str:
        return self.client.messages.batches.retrieve(batch_id).processing_status

    def results(self, batch_id: str) -> Iterable[dict]:
        for entry in self.client.messages.batches.results(batch_id):
            yield entry.model_dump()
