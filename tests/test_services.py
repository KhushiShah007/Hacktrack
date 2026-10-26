"""Unit tests for scoring, clash detector, skill-match, back-planner, eligibility, XP and models."""
from datetime import date, datetime, timedelta

import pytest

from app.models import Hackathon, Internship, Milestone, Opportunity, Scholarship
from app.services import clash, eligibility, planner, scoring, skillmatch, xp

from .conftest import REF


def quest(cls=Hackathon, days=5, **kw):
    return cls(id=kw.pop("id", 1), title=kw.pop("title", "Q"), deadline=(REF + timedelta(days=days)).strftime("%Y-%m-%d %H:%M"), **kw)


# ---------------- models / polymorphism ----------------
def test_factory_picks_subclass_and_stages_are_polymorphic():
    h = Opportunity.create("hackathon", title="H", deadline="2026-11-01")
    i = Opportunity.create("internship", title="I", deadline="2026-11-01")
    assert isinstance(h, Hackathon) and isinstance(i, Internship)
    assert h.stages() == ["PPT Screening", "Prototype", "Finals", "Result"]
    assert i.stages() == ["Applied", "OA", "Interview", "Offer"]
    assert len({tuple(Opportunity.create(t, title="x", deadline="2026-11-01").stages()) for t in Opportunity._registry}) == 6


def test_effort_estimate_override_and_defaults():
    assert Hackathon(title="H", deadline="2026-11-01", team_max=2).effort_estimate() == 48
    assert Hackathon(title="H", deadline="2026-11-01", team_max=4).effort_estimate() == 36
    assert Hackathon(title="H", deadline="2026-11-01", effort_hours=10).effort_estimate() == 10
    assert "Scholarship worth" in Scholarship(title="S", deadline="2026-11-01", prize_text="Rs 1L").describe()


def test_milestone_tree_progress_is_recursive():
    ms = [Milestone(id=1, title="Build"), Milestone(id=2, parent_id=1, done=1), Milestone(id=3, parent_id=1, done=0),
          Milestone(id=4, parent_id=3, done=1), Milestone(id=5, parent_id=3, done=1)]
    roots = Milestone.build_tree(ms)
    assert len(roots) == 1
    assert roots[0].leaf_counts() == (3, 3)  # leaves: 2, 4, 5
    assert roots[0].progress() == 100


# ---------------- priority score ----------------
def test_priority_prefers_urgent_and_valuable():
    soon = quest(days=1, prize_amount=100000, status="registered")
    later = quest(days=30, prize_amount=100000, status="registered")
    cheap = quest(days=1, prize_amount=0, status="registered")
    s_soon, br = scoring.priority_score(soon, 80, REF)
    assert s_soon > scoring.priority_score(later, 80, REF)[0]
    assert s_soon > scoring.priority_score(cheap, 80, REF)[0]
    assert abs(sum(b["points"] for b in br.values()) - s_soon) <= 1
    assert set(br) == {"urgency", "value", "fit", "effort", "status"}


def test_priority_overdue_and_won_are_zeroed():
    overdue = quest(days=-2, status="registered")
    score, br = scoring.priority_score(overdue, 100, REF)
    assert br["urgency"]["factor"] == 0 and br["status"]["factor"] == 0
    won = quest(id=2, days=3, status="won")
    top = scoring.top_n([overdue, won, quest(id=3, days=3)], {}, 5, REF)
    assert [t[0].id for t in top] == [3]


# ---------------- clash detector ----------------
def ev(title, day, kind="quest", prio=50):
    return {"title": title, "when": (REF + timedelta(days=day)).strftime("%Y-%m-%d %H:%M"), "kind": kind,
            "opp_id": 1, "priority": prio, "effort": 12}


def test_clash_week_with_three_deadlines():
    # REF is Monday 26 Oct 2026; 28, 29, 30 Oct share a week
    events = [ev("A", 2, prio=80), ev("B", 3, prio=60), ev("C", 4, prio=10), ev("D", 20)]
    found = clash.detect_clashes(events, REF)
    assert len(found) == 1
    week = found[0]
    assert week["week_start"] == "2026-10-26"
    assert [e["title"] for e in week["deadlines"]] == ["A", "B", "C"]
    assert any("skipping \"C\"" in r for r in week["recommendations"])
    assert any("Start \"A\" early" in r for r in week["recommendations"])


def test_heavy_milestone_week_and_hp():
    events = [ev(f"m{i}", 8, kind="milestone") for i in range(6)]
    found = clash.detect_clashes(events, REF)
    assert found and found[0]["milestone_count"] == 6
    load = clash.weekly_load([ev("A", 1), ev("B", 2), ev("m", 3, "milestone")], REF)
    assert load == {"deadlines": 2, "milestones": 1}
    assert clash.hp_from_load(load) == 100 - 30 - 4
    assert clash.hp_from_load({"deadlines": 20, "milestones": 0}) == 5


def test_no_clash_when_spread_out():
    assert clash.detect_clashes([ev("A", 1), ev("B", 9), ev("C", 17)], REF) == []


# ---------------- skill match ----------------
def test_fit_score_perfect_and_gap():
    req = {"Python": 3, "React": 2}
    perfect = skillmatch.fit_score(req, {"Python": 5, "React": 5})
    weak = skillmatch.fit_score(req, {"Python": 5})
    assert perfect["score"] >= 90 and perfect["gaps"] == []
    assert weak["gaps"] == ["React"] and weak["score"] < perfect["score"]
    assert skillmatch.weighted_jaccard({"a": 1}, {"a": 1}) == 1.0
    assert skillmatch.weighted_jaccard({"a": 1}, {"b": 1}) == 0.0


def test_team_fit_assigns_best_member():
    req = {"Python": 3, "UI/UX": 2, "Blockchain": 2}
    team = {"Riya": {"Python": 5}, "Meera": {"UI/UX": 5, "Python": 2}}
    result = skillmatch.team_fit(req, team)
    by_skill = {a["skill"]: a["member"] for a in result["assignments"]}
    assert by_skill == {"Python": "Riya", "UI/UX": "Meera", "Blockchain": None}
    assert result["gaps"] == ["Blockchain"]
    assert result["score"] > max(result["per_member"].values())


# ---------------- back-planner ----------------
def test_back_plan_works_backwards_from_deadline():
    deadline = REF + timedelta(days=20)
    ms, info = planner.build_plan("hackathon", deadline, 36, REF)
    phases = [m for m in ms if m["depth"] == 0]
    assert [p["title"] for p in phases] == ["Idea", "Research", "Build", "PPT / Report", "Rehearsal", "Buffer"]
    assert phases[-1]["due_date"] == deadline.strftime("%Y-%m-%d %H:%M")
    dues = [p["due_date"] for p in phases]
    assert dues == sorted(dues)
    for m in ms:  # every child is due on or before its parent phase
        if m["parent"] is not None:
            assert m["due_date"] <= ms[m["parent"]]["due_date"]
            assert m["parent"] < ms.index(m)
    assert not info["compressed"] and info["span_days"] == 18  # 36h / 3h per day = 12, x1.5


def test_back_plan_compresses_when_deadline_is_close():
    ms, info = planner.build_plan("internship", REF + timedelta(days=2), 30, REF)
    assert info["compressed"] and info["span_days"] == 2
    assert all(m["due_date"] >= REF.strftime("%Y-%m-%d %H:%M") for m in ms)


def test_back_plan_needs_deadline():
    with pytest.raises(ValueError):
        planner.build_plan("hackathon", None, 10, REF)


# ---------------- eligibility ----------------
@pytest.mark.parametrize("rules,user,verdict", [
    ({}, {"year": 2, "branch": "CSE", "college": "X"}, "Eligible"),
    ({"eligibility_text": "Women only"}, {"year": 2}, "Check manually"),
    ({"eligible_years": "1"}, {"year": 3, "branch": "CSE", "college": "X"}, "Not eligible"),
    ({"eligible_years": "2,3", "eligible_branches": "CSE,IT"}, {"year": 3, "branch": "IT", "college": "X"}, "Eligible"),
    ({"eligible_branches": "ECE"}, {"year": 3, "branch": "CSE", "college": "X"}, "Not eligible"),
    ({"eligible_colleges": "IIT,NIT"}, {"year": 1, "branch": "CSE", "college": "Chitkara University"}, "Not eligible"),
    ({"eligible_colleges": "IIT"}, {"year": 1, "branch": "CSE", "college": "IIT Delhi"}, "Eligible"),
    ({"eligible_years": "2"}, {"year": None, "branch": "CSE", "college": "X"}, "Check manually"),
])
def test_eligibility(rules, user, verdict):
    opp = Hackathon(title="E", deadline="2026-12-01", **rules)
    got, reason = eligibility.check(user, opp)
    assert got == verdict and reason


# ---------------- XP, levels, streaks ----------------
def test_levels_and_titles():
    assert xp.level_for_xp(0) == 1 and xp.level_for_xp(99) == 1 and xp.level_for_xp(100) == 2
    assert xp.level_for_xp(300) == 3 and xp.level_title(3) == "Challenger"
    assert xp.level_title(10) == "Champion" and xp.level_title(20) == "Legend"
    p = xp.progress(150)
    assert p["level"] == 2 and p["into"] == 50 and p["needed"] == 200 and p["pct"] == 25


def test_streak_recursion():
    today = date(2026, 10, 26)
    days = {today - timedelta(days=i) for i in range(5)} | {today - timedelta(days=9)}
    assert xp.current_streak(days, today) == 5
    assert xp.current_streak(days - {today}, today) == 4  # yesterday still counts
    assert xp.current_streak({today - timedelta(days=3)}, today) == 0
    assert xp.longest_streak(days) == 5


def test_award_once_and_badges(db, demo_id):
    before = xp.total_xp(db, demo_id)
    r1 = xp.award(db, demo_id, "trophy", "test-ref", once=True)
    r2 = xp.award(db, demo_id, "trophy", "test-ref", once=True)
    assert r1["points"] == 150 and r2["points"] == 0
    assert xp.total_xp(db, demo_id) == before + 150
    assert xp.award(db, demo_id, "not-a-rule")["points"] == 0
    db.execute("DELETE FROM user_badges WHERE user_id = ?", (demo_id,))
    new = xp.check_badges(db, demo_id)
    assert "Winner" in new and "Quest Accepted" in new
    assert xp.check_badges(db, demo_id) == []
