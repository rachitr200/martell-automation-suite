import json
import threading
import urllib.request

from copilot_api.patterns import (
    build_playbook,
    classify_objection,
    ngrams,
    objection_replies,
    winning_phrases,
)
from copilot_api.server import make_server
from copilot_api.suggest import suggest_reply

import pathlib

DATA = json.loads((pathlib.Path(__file__).resolve().parents[1] / "data" / "sample_conversations.json").read_text())


def test_objection_classification():
    assert classify_objection("honestly that's too much for us") == "price"
    assert classify_objection("Not now, maybe next month") == "timing"
    assert classify_objection("let me run it by my partner") == "think_about_it"
    assert classify_objection("we already use HubSpot") == "competitor"
    assert classify_objection("sounds great, let's go") is None


def test_ngrams_skip_pure_stopword_phrases():
    grams = ngrams("we can do it for you")
    assert "we can" not in grams and "can do" not in grams


def test_winning_phrases_prefer_won_only_language():
    phrases = {r["phrase"]: r for r in winning_phrases(DATA, min_support=2)}
    assert "quick call" in phrases and phrases["quick call"]["lost"] == 0
    assert phrases["quick call"]["lift"] > 0


def test_support_floor_filters_one_off_phrases():
    assert all(r["won"] >= 3 for r in winning_phrases(DATA, min_support=3))


def test_objection_replies_come_only_from_won_conversations():
    replies = objection_replies(DATA)
    ids = {r["conversation"] for rs in replies.values() for r in rs}
    assert ids and all(i.startswith("w") for i in ids)
    assert set(replies) >= {"price", "timing", "think_about_it", "competitor"}


def test_playbook_stats():
    assert build_playbook(DATA)["stats"] == {"won": 5, "lost": 4}


def test_suggestions_without_llm_are_real_won_replies():
    playbook = build_playbook(DATA)
    out = suggest_reply(playbook, [{"role": "prospect", "text": "that's a bit expensive"}])
    assert out["objection"] == "price"
    assert all(s["source"] == "won_deal" and s["conversation"].startswith("w") for s in out["suggestions"])


def test_llm_draft_is_grounded_in_examples_and_constrained():
    seen = {}

    def fake_llm(system, user):
        seen.update(system=system, user=user)
        return " Happy to walk you through it. "

    out = suggest_reply(build_playbook(DATA), [{"role": "prospect", "text": "too much money for us"}], llm=fake_llm)
    assert out["suggestions"][0] == {"source": "ai_draft", "text": "Happy to walk you through it."}
    assert "recoup the cost" in seen["user"]  # a winning example was supplied
    assert "Never invent prices" in seen["system"]


def test_graceful_when_no_examples_or_no_prospect_message():
    assert suggest_reply(build_playbook(DATA), [{"role": "prospect", "text": "hello there"}])["suggestions"] == []
    assert suggest_reply(build_playbook(DATA), [{"role": "rep", "text": "hi"}])["note"]


def test_http_api_round_trip_and_validation():
    server = make_server(build_playbook(DATA), port=0)  # port 0: the OS picks a free one
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{port}"
        assert json.load(urllib.request.urlopen(f"{base}/health"))["won"] == 5

        body = json.dumps({"messages": [{"role": "prospect", "text": "it's too expensive"}]}).encode()
        req = urllib.request.Request(f"{base}/suggest", data=body, headers={"Content-Type": "application/json"})
        result = json.load(urllib.request.urlopen(req))
        assert result["objection"] == "price" and result["suggestions"]

        bad = urllib.request.Request(f"{base}/suggest", data=b'{"nope": 1}', headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(bad)
            raise AssertionError("expected HTTP 400")
        except urllib.error.HTTPError as err:
            assert err.code == 400
    finally:
        server.shutdown()
        server.server_close()
