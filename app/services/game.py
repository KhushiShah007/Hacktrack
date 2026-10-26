"""Glue between the database and the game layer: HUD numbers, rewards, map pins, calendar events."""
from datetime import timedelta

from flask import g, session

from ..db import get_db
from ..models import Milestone, Opportunity, User
from ..utils import days_left, now as _now, parse_dt, countdown
from . import clash, scoring, skillmatch, xp as xp_service


def user_fits(db, user):
    """Skill-fit score for each of the user's quests in two queries (JOIN + GROUP BY in SQL)."""
    skills = User(id=user.id).skills(db)
    rows = db.execute(
        "SELECT os.opportunity_id, s.name, os.importance FROM opportunity_skills os "
        "JOIN skills s ON s.id = os.skill_id JOIN opportunities o ON o.id = os.opportunity_id "
        "WHERE o.user_id = ?", (user.id,)).fetchall()
    required = {}
    for r in rows:
        required.setdefault(r["opportunity_id"], {})[r["name"]] = r["importance"]
    opp_ids = [r["id"] for r in db.execute("SELECT id FROM opportunities WHERE user_id = ?", (user.id,))]
    return {oid: skillmatch.fit_score(required.get(oid, {}), skills)["score"] for oid in opp_ids}


def calendar_events(db, user, ref=None):
    """Every dated thing for a user: quest deadlines, pending rounds and open milestones."""
    fits = user_fits(db, user)
    opps = {o.id: o for o in Opportunity.for_user(db, user.id)}
    events = []
    for o in opps.values():
        if o.status in ("won", "rejected", "submitted"):
            continue
        prio = scoring.priority_score(o, fits.get(o.id, 60), ref)[0]
        events.append({"title": o.title, "when": o.deadline, "kind": "quest", "opp_id": o.id,
                       "priority": prio, "effort": o.effort_estimate(), "type": o.type})
    for r in db.execute("SELECT r.*, o.title AS qtitle FROM rounds r JOIN opportunities o ON o.id = r.opportunity_id "
                        "WHERE o.user_id = ? AND r.status = 'pending' AND o.status NOT IN ('won','rejected')", (user.id,)):
        if r["deadline"] == opps.get(r["opportunity_id"], Opportunity()).deadline:
            continue  # round on the same day as the quest deadline is the same event
        o = opps.get(r["opportunity_id"])
        events.append({"title": f"{r['qtitle']}: {r['name']}", "when": r["deadline"], "kind": "round",
                       "opp_id": r["opportunity_id"], "priority": scoring.priority_score(o, fits.get(o.id, 60), ref)[0] if o else 0,
                       "effort": 6, "type": o.type if o else ""})
    for m in db.execute("SELECT m.*, o.title AS qtitle FROM milestones m JOIN opportunities o ON o.id = m.opportunity_id "
                        "WHERE o.user_id = ? AND m.done = 0 AND m.parent_id IS NOT NULL", (user.id,)):
        events.append({"title": f"{m['qtitle']}: {m['title']}", "when": m["due_date"], "kind": "milestone",
                       "opp_id": m["opportunity_id"], "priority": 0, "effort": 2, "type": ""})
    return events


def hud(db, user):
    total = xp_service.total_xp(db, user.id)
    prog = xp_service.progress(total)
    streak = xp_service.current_streak(xp_service.active_days(db, user.id))
    load = clash.weekly_load(calendar_events(db, user))
    unread = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (user.id,)).fetchone()[0]
    return {**prog, "streak": streak, "hp": clash.hp_from_load(load), "load": load, "unread": unread}


def reward(action, ref="", once=False):
    """Award XP to the logged-in player, check badges and queue pop-ups. Returns list of pop-ups."""
    db = get_db()
    user_id = g.user.id
    result = xp_service.award(db, user_id, action, ref, once=once)
    popups = []
    if result["points"]:
        popups.append({"kind": "xp", "text": f"+{result['points']} XP"})
    if result.get("level_up"):
        popups.append({"kind": "level", "text": f"LEVEL UP! Level {result['level']}: {result['title']}"})
    for name in xp_service.check_badges(db, user_id):
        popups.append({"kind": "badge", "text": f"Badge unlocked: {name}"})
    queue = session.get("popups", [])
    session["popups"] = (queue + popups)[-6:]
    return popups


def quest_state(opp, ref=None):
    if opp.status == "won":
        return "won"
    if opp.status == "rejected":
        return "missed"
    if opp.status in ("submitted", "shortlisted"):
        return "done"
    d = days_left(opp.deadline, ref)
    if d is not None and d < 0:
        return "missed"
    return "pending"


PIN_VARIANT = {"pending": "red", "done": "green", "won": "gold", "locked": "grey", "missed": "missed"}


def world_map_pins(db, user, ref=None):
    """Active quests plus anything resolved in the last 30 days, ordered by deadline."""
    ref = ref or _now()
    since = (ref - timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
    opps = Opportunity.for_user(
        db, user.id,
        "AND (status IN ('interested','preparing','registered') OR deadline >= ?)",
        (since,))
    opps = [o for o in opps if not (o.is_open and days_left(o.deadline, ref) < -30)]
    fits = user_fits(db, user)
    pins = []
    for o in opps:
        state = quest_state(o, ref)
        leaves = [m for m in o.milestones(db) if m.parent_id]
        done = sum(m.done for m in leaves)
        pins.append({"id": o.id, "kind": "quest", "title": o.title, "type": o.type, "label": o.label,
                     "state": state, "variant": PIN_VARIANT[state], "status": o.status, "status_label": o.status_label,
                     "countdown": o.countdown(ref) if state == "pending" else o.status_label,
                     "urgency": o.urgency(ref), "deadline": o.deadline, "organizer": o.organizer,
                     "prize": o.prize_text, "team": o.team_text(), "mode": o.mode, "fit": fits.get(o.id, 60),
                     "priority": scoring.priority_score(o, fits.get(o.id, 60), ref)[0],
                     "progress": round(100 * done / len(leaves)) if leaves else None,
                     "next": [{"id": m.id, "title": m.title, "due": m.due_date, "done": m.done}
                              for m in leaves if not m.done][:5],
                     "url": f"/quests/{o.id}", "map_url": f"/quests/{o.id}/map"})
    return pins


def roadmap_pins(opp, rounds, milestones, ref=None):
    """One quest's rounds and top-level back-plan phases, merged by date; future ones are locked."""
    ref = ref or _now()
    roots = Milestone.build_tree(milestones)
    pins = []
    for m in roots:
        pct = m.progress()
        state = "done" if pct == 100 else "pending"
        pins.append({"id": m.id, "kind": "phase", "title": m.title, "type": "", "label": "Back-plan phase",
                     "state": state, "progress": pct, "deadline": m.due_date,
                     "countdown": f"{pct}% done" if state == "done" else countdown(m.due_date, ref),
                     "children": [{"id": c.id, "title": c.title, "done": c.done, "due": c.due_date} for c in m.children]})
    for r in rounds:
        state = {"cleared": "done", "skipped": "done", "failed": "missed"}.get(r.status, "pending")
        pins.append({"id": r.id, "kind": "round", "title": r.name, "type": "", "label": f"Round {r.seq}",
                     "state": state, "deadline": r.deadline, "status": r.status,
                     "countdown": r.status.title() if state != "pending" else countdown(r.deadline, ref)})
    pins.sort(key=lambda p: (parse_dt(p["deadline"]) or ref, 0 if p["kind"] == "phase" else 1))
    seen_pending = False
    for p in pins:
        if p["state"] == "pending":
            if seen_pending:
                p["state"] = "locked"
            seen_pending = True
        p["variant"] = PIN_VARIANT[p["state"]]
    return pins
