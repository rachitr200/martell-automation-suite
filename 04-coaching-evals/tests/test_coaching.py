from pathlib import Path

from coaching_ai.assistant import REFUSAL, REFUSAL_MARKER, CoachingAssistant
from coaching_ai.cli import stub_llm
from coaching_ai.evals import load_cases, pass_rate, run_case, run_suite
from coaching_ai.kb import Index, load_dir, tokenize

ROOT = Path(__file__).resolve().parents[1]


def make(llm=stub_llm, **kw):
    return CoachingAssistant(Index(load_dir(ROOT / "knowledge")), llm, **kw)


def test_tokenizer_drops_stopwords():
    assert tokenize("How do I delegate the tasks?") == ["delegat", "task"]  # stemmed


def test_chunks_have_stable_citation_ids():
    ids = [c.id for c in load_dir(ROOT / "knowledge")]
    assert "time_audit#1" in ids and len(ids) == len(set(ids))


def test_retrieval_finds_the_right_document():
    top = Index(load_dir(ROOT / "knowledge")).search("when should I hire an operations person", k=1)
    assert top[0][0].doc == "first_operations_hire"


def test_out_of_scope_question_is_refused_without_calling_the_llm():
    calls = []
    assistant = make(llm=lambda s, u: calls.append(1) or "x")
    ans = assistant.ask("What is the weather in Paris?")
    assert ans.refused and ans.text == REFUSAL and calls == []


def test_prompt_contains_only_retrieved_context_and_rules():
    seen = {}
    make(llm=lambda s, u: seen.update(system=s) or "ok").ask("how do I price my program")
    assert "[pricing_basics#" in seen["system"] and "ONLY from the context" in seen["system"]
    assert "[time_audit#" not in seen["system"]  # unrelated docs stay out of the prompt


def test_invalid_citations_are_detected():
    ans = make(llm=lambda s, u: "Do X [made_up#9] and Y [pricing_basics#1]").ask("how do I price my program")
    assert ans.invalid_citations == ["made_up#9"]
    assert "pricing_basics#1" in ans.cited


def test_eval_harness_catches_a_fabricating_model():
    assistant = make(llm=lambda s, u: "Studies prove this works [pricing_basics#1] ironclad guarantee")
    case = {"question": "how do I price my program", "must_not_include": ["guarantee"]}
    assert any("forbidden" in f for f in run_case(assistant, case).failures)


def test_eval_harness_catches_uncited_answers():
    assistant = make(llm=lambda s, u: "Just charge more.")
    case = {"question": "how do I price my program", "must_cite": True}
    assert any("no citations" in f for f in run_case(assistant, case).failures)


def test_full_suite_passes_with_the_stub_model():
    results = run_suite(make(), load_cases(ROOT / "evals" / "cases.jsonl"))
    failures = [(r.question, r.failures) for r in results if not r.passed]
    assert not failures, failures


def test_model_refusal_cases_are_skipped_offline_and_judged_live():
    case = {"question": "Which cryptocurrency should I buy this week?", "expect_refusal": True, "refusal_by": "model"}
    assert run_case(make(), case).skipped  # stub model can't prove anything here

    declines = make(llm=lambda s, u: f"Sorry, I {REFUSAL_MARKER} for that.")
    fabricates = make(llm=lambda s, u: "Buy Bitcoin now.")
    assert run_case(declines, case, live=True).passed
    assert not run_case(fabricates, case, live=True).passed


def test_pass_rate_ignores_skipped_cases():
    results = run_suite(make(), load_cases(ROOT / "evals" / "cases.jsonl"))
    assert any(r.skipped for r in results) and pass_rate(results) == 1.0


def test_gate_threshold_is_a_coarse_filter_not_a_scope_classifier():
    # Documented limitation: a short question sharing one generic word can reach the model.
    index = Index(load_dir(ROOT / "knowledge"))
    best = max(index.coverage("Which cryptocurrency should I buy this week?", c) for c, _ in
               index.search("Which cryptocurrency should I buy this week?", 3))
    assert best >= 0.3  # passes the gate; the live eval, not the gate, is what protects this case
