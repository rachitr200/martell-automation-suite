from pathlib import Path

from team_leverage.requests_log import rank, report

SAMPLE = (Path(__file__).resolve().parents[1] / "request_log.sample.csv").read_text()


def test_ranked_by_total_minutes_not_by_count():
    top = rank(SAMPLE)[0]
    assert top.category == "why did a member not get access"
    assert (top.count, top.total_minutes, top.requesters) == (5, 135, 3)


def test_action_scales_with_repetition_and_spread():
    actions = {o.category: o.action for o in rank(SAMPLE)}
    assert actions["why did a member not get access"].startswith("build a self-serve")
    assert actions["export contacts for a campaign"].startswith("write a how-to")
    assert actions["what does this zap do"].startswith("one-off")


def test_five_asks_from_one_person_is_not_a_tool_it_is_a_habit():
    rows = "date,requester,category,minutes\n" + "\n".join(f"2026-10-0{i},sam,thing,10" for i in range(1, 6))
    assert rank(rows)[0].action.startswith("write a how-to")


def test_categories_are_case_and_space_insensitive():
    rows = "date,requester,category,minutes\n2026-10-01,a, Thing ,5\n2026-10-02,b,thing,5\n"
    assert rank(rows)[0].count == 2


def test_report_renders_a_table():
    assert "category" in report(rank(SAMPLE)).splitlines()[0]
