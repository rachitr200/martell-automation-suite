from __future__ import annotations

import time
from collections.abc import Callable

from batch_classifier.backend import BatchBackend
from batch_classifier.batch import Prediction, build_requests, parse_results


def classify(
    conversations: list[dict],
    backend: BatchBackend,
    model: str,
    poll_seconds: float = 30.0,
    max_wait_seconds: float = 24 * 3600,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Prediction]:
    batch_id = backend.submit(build_requests(conversations, model))
    waited = 0.0
    while backend.status(batch_id) != "ended":
        if waited >= max_wait_seconds:
            raise TimeoutError(f"batch {batch_id} still running after {max_wait_seconds}s")
        sleep(poll_seconds)
        waited += poll_seconds
    predictions = parse_results(backend.results(batch_id))
    missing = {c["id"] for c in conversations} - predictions.keys()
    for cid in missing:  # a request with no result must be visible, never silently dropped
        predictions[cid] = Prediction("error", "no result returned", "missing")
    return predictions
