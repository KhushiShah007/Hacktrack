"""Clash Detector: weeks with 3+ deadlines or a heavy milestone load, with advice."""
from collections import defaultdict
from datetime import timedelta

from ..utils import parse_dt, now as _now, week_start


def detect_clashes(events, ref=None, min_deadlines=3, heavy_milestones=6, horizon_weeks=10):
    """events: dicts with title, when, kind ('quest'|'round'|'milestone'), opp_id, priority, effort.

    Returns a list of clash weeks, each with recommendations. # CO1 lambda/filter
    """
    ref = ref or _now()
    limit = ref + timedelta(weeks=horizon_weeks)
    upcoming = list(filter(lambda e: parse_dt(e["when"]) and ref <= parse_dt(e["when"]) <= limit, events))
    deadlines, milestones = defaultdict(list), defaultdict(list)
    for e in upcoming:
        bucket = milestones if e["kind"] == "milestone" else deadlines
        bucket[week_start(e["when"])].append(e)

    clashes = []
    for week in sorted(set(deadlines) | set(milestones)):
        dls, mss = deadlines.get(week, []), milestones.get(week, [])
        if len(dls) < min_deadlines and len(mss) < heavy_milestones:
            continue
        ranked = sorted(dls, key=lambda e: e.get("priority", 0), reverse=True)
        recs = []
        for e in ranked[:2]:
            hours = e.get("effort", 10)
            start = parse_dt(e["when"]) - timedelta(days=max(2, round(hours / 3)) + 2)
            start = max(start, ref)
            recs.append(f"Start \"{e['title']}\" early: begin by {start.strftime('%a %d %b')}.")
        if len(ranked) >= min_deadlines:
            weakest = ranked[-1]
            recs.append(f"Consider skipping \"{weakest['title']}\" (lowest priority {weakest.get('priority', 0)}).")
        if len(mss) >= heavy_milestones:
            recs.append(f"{len(mss)} milestones land this week; tick a few off the week before.")
        severity = "critical" if len(dls) >= min_deadlines + 2 else ("high" if len(dls) >= min_deadlines else "medium")
        clashes.append({
            "week_start": week.strftime("%Y-%m-%d"),
            "week_label": f"{week.strftime('%d %b')} - {(week + timedelta(days=6)).strftime('%d %b')}",
            "deadlines": sorted(dls, key=lambda e: parse_dt(e["when"])),
            "milestone_count": len(mss),
            "severity": severity,
            "recommendations": recs,
        })
    return clashes


def weekly_load(events, ref=None):
    """Counts of deadlines and milestones in the next 7 days."""
    ref = ref or _now()
    end = ref + timedelta(days=7)
    soon = [e for e in events if parse_dt(e["when"]) and ref <= parse_dt(e["when"]) <= end]
    return {
        "deadlines": sum(1 for e in soon if e["kind"] != "milestone"),
        "milestones": sum(1 for e in soon if e["kind"] == "milestone"),
    }


def hp_from_load(load):
    """HP drops as the week fills up: each deadline costs 15, each milestone 4."""
    hp = 100 - load["deadlines"] * 15 - load["milestones"] * 4
    return max(5, min(100, hp))
