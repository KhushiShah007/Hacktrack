"""Auto Back-Planner: works backwards from a deadline to a dated milestone tree.

Templates are trees of phases (idea, research, build, PPT/report, rehearsal, buffer). The
scheduler walks the tree recursively: each node's time span is split between its children in
proportion to their `share`, starting from the deadline and moving backwards.
"""
import math
from datetime import datetime, timedelta

from ..utils import parse_dt, now as _now

HOURS_PER_DAY = 3  # realistic study-time a student can put in alongside classes


def _n(title, share, *children):
    return {"title": title, "share": share, "children": list(children)}


TEMPLATES = {
    "hackathon": [
        _n("Idea", 0.10, _n("Brainstorm problem statements", 1), _n("Pick idea and split team roles", 1)),
        _n("Research", 0.15, _n("Study judging criteria and past winners", 1), _n("Research APIs and datasets", 1)),
        _n("Build", 0.45, _n("Core MVP working end to end", 2), _n("Integrate and polish UI", 1), _n("Test and fix bugs", 1)),
        _n("PPT / Report", 0.15, _n("Draft pitch deck", 1), _n("Record demo video", 1)),
        _n("Rehearsal", 0.05, _n("Timed dry-run of the pitch", 1)),
        _n("Buffer", 0.10, _n("Final submission with buffer time", 1)),
    ],
    "competition": [
        _n("Research", 0.15, _n("Read rules and format", 1), _n("Review past problems", 1)),
        _n("Practice", 0.45, _n("Topic-wise practice", 2), _n("Timed mock round", 1)),
        _n("Report", 0.20, _n("Prepare submission / notes", 1)),
        _n("Rehearsal", 0.10, _n("Full mock under exam conditions", 1)),
        _n("Buffer", 0.10, _n("Submit with buffer time", 1)),
    ],
    "internship": [
        _n("Research", 0.15, _n("Read the job description", 1), _n("Research the company and team", 1)),
        _n("Resume", 0.20, _n("Tailor resume to the role", 1), _n("Ask for a referral", 1)),
        _n("Prep", 0.45, _n("DSA practice set", 2), _n("Project walkthrough script", 1), _n("Mock interview", 1)),
        _n("Rehearsal", 0.10, _n("Behavioural answers rehearsal", 1)),
        _n("Buffer", 0.10, _n("Submit application with buffer", 1)),
    ],
    "scholarship": [
        _n("Research", 0.15, _n("Confirm eligibility", 1), _n("List required documents", 1)),
        _n("Documents", 0.30, _n("Collect marksheets and certificates", 1), _n("Request recommendation letters", 1)),
        _n("Essay", 0.35, _n("Draft statement of purpose", 1), _n("Revise SOP with feedback", 1)),
        _n("Review", 0.10, _n("Proof-read the whole application", 1)),
        _n("Buffer", 0.10, _n("Submit with buffer time", 1)),
    ],
    "workshop": [
        _n("Register", 0.20, _n("Register and join the group", 1)),
        _n("Prep", 0.40, _n("Install the tools", 1), _n("Do the pre-reading", 1)),
        _n("Assignment", 0.30, _n("Finish the workshop assignment", 1)),
        _n("Buffer", 0.10, _n("Collect certificate", 1)),
    ],
    "research": [
        _n("Idea", 0.15, _n("Read 3 recent papers", 1), _n("Identify a research gap", 1)),
        _n("Research", 0.25, _n("Shortlist labs and professors", 1), _n("Write cold emails", 1)),
        _n("Proposal", 0.35, _n("Draft the proposal", 2), _n("Get feedback from a mentor", 1)),
        _n("Rehearsal", 0.10, _n("Prepare for the interview", 1)),
        _n("Buffer", 0.15, _n("Submit with buffer time", 1)),
    ],
}


def plan_span_days(effort_hours, available_days):
    """Days the plan should cover; compressed when the deadline is too close."""
    needed = max(3, math.ceil(effort_hours / HOURS_PER_DAY))
    if available_days < needed:
        return max(available_days, 1), True
    # never start absurdly early: cap at 1.5x what the work needs
    return min(available_days, math.ceil(needed * 1.5)), False


def _schedule(nodes, end, span_days, depth, parent_idx, phase, out):
    """Recursively place `nodes` backwards from `end` across `span_days`. # CO1 recursion"""
    total_share = sum(n["share"] for n in nodes) or 1
    cursor = end
    placed = []
    for node in reversed(nodes):
        child_span = span_days * node["share"] / total_share
        placed.append((node, cursor, child_span))
        cursor = cursor - timedelta(days=child_span)
    for node, node_end, child_span in reversed(placed):  # emit in chronological pre-order
        idx = len(out)
        out.append({
            "title": node["title"],
            "phase": phase or node["title"],
            "due": node_end,
            "depth": depth,
            "parent": parent_idx,
        })
        if node["children"]:
            _schedule(node["children"], node_end, child_span, depth + 1, idx, phase or node["title"], out)
    return out


def build_plan(opp_type, deadline, effort_hours, today=None):
    """Return (milestones, info). Milestones are in parent-before-child order. # CO1 # CO2"""
    today = today or _now()
    deadline = parse_dt(deadline)
    if deadline is None:
        raise ValueError("deadline is required for back-planning")
    available = max((deadline.date() - today.date()).days, 0)
    span, compressed = plan_span_days(effort_hours, available)
    template = TEMPLATES.get(opp_type, TEMPLATES["hackathon"])
    raw = _schedule(template, deadline, span, 0, None, None, [])
    milestones = []
    for item in raw:
        due = item["due"]
        if due < deadline:
            due = due.replace(hour=18, minute=0)  # evening slot except the final deadline
        due = max(due, today)
        milestones.append({**item, "due_date": due.strftime("%Y-%m-%d %H:%M")})
    info = {
        "start": (deadline - timedelta(days=span)).strftime("%Y-%m-%d"),
        "span_days": span,
        "compressed": compressed,
        "hours_per_day": round(effort_hours / max(span, 1), 1),
    }
    return milestones, info


def save_plan(db, opportunity_id, milestones):
    """Replace a quest's milestones with a freshly generated tree (DML). # CO3"""
    db.execute("DELETE FROM milestones WHERE opportunity_id = ?", (opportunity_id,))
    ids = []
    for seq, m in enumerate(milestones):
        parent_id = ids[m["parent"]] if m["parent"] is not None else None
        cur = db.execute(
            "INSERT INTO milestones (opportunity_id, parent_id, title, phase, due_date, seq) VALUES (?, ?, ?, ?, ?, ?)",
            (opportunity_id, parent_id, m["title"], m["phase"], m["due_date"], seq))
        ids.append(cur.lastrowid)
    db.commit()
    return ids
