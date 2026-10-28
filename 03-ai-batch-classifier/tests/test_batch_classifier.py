import json

from batch_classifier import baseline
from batch_classifier.backend import FakeBackend
from batch_classifier.batch import build_requests, parse_label, parse_results
from batch_classifier.data import load_eval_set
from batch_classifier.evals import evaluate
from batch_classifier.runner import classify


def conv(i="c1", text="hello"):
    return {"id": i, "messages": [{"role": "customer", "text": text}]}


def test_request_shape_matches_batch_api():
    reqs = build_requests([conv("a-1")], model="m")
    assert reqs[0]["custom_id"] == "a-1"
    params = reqs[0]["params"]
    assert params["model"] == "m" and params["messages"][0]["role"] == "user"
    assert "Customer: hello" in params["messages"][0]["content"]


def test_invalid_custom_id_is_rejected_before_submit():
    for bad in ("has space", "x" * 65, "dots.not.allowed"):
        try:
            build_requests([conv(bad)], model="m")
        except ValueError:
            continue
        raise AssertionError(f"{bad!r} should have been rejected")


def test_parse_label_tolerates_fences_and_chatter():
    assert parse_label('```json\n{"label": "churn_risk", "reason": "wants to cancel"}\n```')[0] == "churn_risk"
    assert parse_label('Sure! {"label": "support_issue", "reason": "x"} hope that helps')[0] == "support_issue"


def test_parse_label_flags_unknown_labels_and_garbage():
    assert parse_label('{"label": "angry", "reason": "x"}')[0] == "unparseable"
    assert parse_label("no json here")[0] == "unparseable"


def test_non_succeeded_results_become_visible_errors():
    entries = [
        {"custom_id": "a", "result": {"type": "errored", "error": {"type": "overloaded"}}},
        {"custom_id": "b", "result": {"type": "expired"}},
    ]
    out = parse_results(entries)
    assert out["a"].label == "error" and out["a"].status == "errored"
    assert out["b"].status == "expired"


def test_pipeline_end_to_end_with_fake_backend_and_polling():
    sleeps = []
    backend = FakeBackend(lambda req: json.dumps({"label": "general_question", "reason": "r"}), polls_until_done=2)
    preds = classify([conv("a"), conv("b")], backend, "m", poll_seconds=5, sleep=sleeps.append)
    assert {k: v.label for k, v in preds.items()} == {"a": "general_question", "b": "general_question"}
    assert sleeps == [5, 5]  # polled twice before the batch ended


def test_missing_results_are_reported_not_dropped():
    class Dropping(FakeBackend):
        def results(self, batch_id):
            return list(super().results(batch_id))[:1]

    backend = Dropping(lambda req: '{"label": "churn_risk", "reason": "r"}', polls_until_done=0)
    preds = classify([conv("a"), conv("b")], backend, "m", sleep=lambda s: None)
    assert preds["b"].label == "error" and preds["b"].status == "missing"


def test_timeout_when_batch_never_ends():
    class Stuck(FakeBackend):
        def status(self, batch_id):
            return "in_progress"

    try:
        classify([conv()], Stuck(lambda r: ""), "m", poll_seconds=10, max_wait_seconds=30, sleep=lambda s: None)
    except TimeoutError:
        return
    raise AssertionError("expected TimeoutError")


def test_eval_scoring_math():
    gold = {"1": "a", "2": "a", "3": "b", "4": "b"}
    report = evaluate({"1": "a", "2": "b", "3": "b"}, gold)  # 4 is missing
    assert report.accuracy == 0.5
    assert report.per_label["a"]["precision"] == 1.0 and report.per_label["a"]["recall"] == 0.5
    assert report.per_label["b"]["precision"] == 0.5 and report.per_label["b"]["recall"] == 0.5
    assert ("4", "b", "missing") in report.misses


def test_baseline_is_a_real_but_imperfect_control():
    conversations, gold = load_eval_set()
    report = evaluate(baseline.classify_all(conversations), gold)
    assert 0.7 <= report.accuracy < 1.0  # strong on obvious cases, fails the hard ones on purpose
    assert report.misses  # so an LLM has headroom to prove its value
