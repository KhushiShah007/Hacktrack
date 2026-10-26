"""XP, levels, streaks and badges (the game layer)."""
import logging
from datetime import date, timedelta

from ..constants import LEVEL_TITLES, XP_RULES

log = logging.getLogger("hacktrack.xp")


def xp_for_level(level):
    """Cumulative XP needed to reach `level`: 0, 100, 300, 600, 1000, ..."""
    return 50 * level * (level - 1)


def level_for_xp(xp):
    level = 1
    while xp >= xp_for_level(level + 1):
        level += 1
    return level


def level_title(level):
    title = LEVEL_TITLES[0][1]
    for min_level, name in LEVEL_TITLES:
        if level >= min_level:
            title = name
    return title


def progress(xp):
    level = level_for_xp(xp)
    lo, hi = xp_for_level(level), xp_for_level(level + 1)
    return {
        "xp": xp, "level": level, "title": level_title(level),
        "into": xp - lo, "needed": hi - lo, "next_at": hi,
        "pct": round(100 * (xp - lo) / (hi - lo)),
    }


def streak_from(day, active_days):
    """Recursively count consecutive active days ending at `day`. # CO1 recursion"""
    if day not in active_days:
        return 0
    return 1 + streak_from(day - timedelta(days=1), active_days)


def current_streak(active_days, today=None):
    today = today or date.today()
    days = set(active_days)
    # a streak is still alive if you were active yesterday and haven't acted yet today
    return streak_from(today, days) or streak_from(today - timedelta(days=1), days)


def longest_streak(active_days):
    days = sorted(set(active_days))
    best = run = 0
    prev = None
    for d in days:
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    return best


def total_xp(db, user_id):
    return db.execute("SELECT COALESCE(SUM(points),0) FROM xp_events WHERE user_id = ?", (user_id,)).fetchone()[0]


def active_days(db, user_id):
    rows = db.execute("SELECT DISTINCT date(created_at) AS d FROM xp_events WHERE user_id = ?", (user_id,)).fetchall()
    return {date.fromisoformat(r["d"]) for r in rows if r["d"]}


def award(db, user_id, action, ref="", once=False, when=None):
    """Insert an xp_event and return {'points', 'level_up', 'level'}; `once` dedupes on action+ref. # CO3"""
    points = XP_RULES.get(action, 0)
    if not points:
        return {"points": 0, "level_up": False}
    if once and db.execute("SELECT 1 FROM xp_events WHERE user_id=? AND action=? AND ref=?",
                           (user_id, action, str(ref))).fetchone():
        return {"points": 0, "level_up": False}
    before = level_for_xp(total_xp(db, user_id))
    if when:
        db.execute("INSERT INTO xp_events (user_id, action, points, ref, created_at) VALUES (?,?,?,?,?)",
                   (user_id, action, points, str(ref), when))
    else:
        db.execute("INSERT INTO xp_events (user_id, action, points, ref) VALUES (?,?,?,?)",
                   (user_id, action, points, str(ref)))
    after = level_for_xp(total_xp(db, user_id))
    if after > before:
        db.execute("INSERT OR IGNORE INTO notifications (user_id, kind, message, link, dedupe_key) VALUES (?,?,?,?,?)",
                   (user_id, "level", f"LEVEL UP! You reached level {after}: {level_title(after)}.", "/dashboard",
                    f"level-{after}"))
    db.commit()
    return {"points": points, "level_up": after > before, "level": after, "title": level_title(after)}


BADGE_RULES = {
    "first_quest": "SELECT COUNT(*) >= 1 FROM opportunities WHERE user_id = :u",
    "first_submission": "SELECT COUNT(*) >= 1 FROM opportunities WHERE user_id = :u AND status IN ('submitted','shortlisted','won')",
    "finalist": "SELECT COUNT(*) >= 1 FROM opportunities WHERE user_id = :u AND status IN ('shortlisted','won')",
    "winner": "SELECT COUNT(*) >= 1 FROM opportunities WHERE user_id = :u AND status = 'won'",
    "five_in_month": """SELECT COALESCE(MAX(c), 0) >= 5 FROM (
                          SELECT strftime('%Y-%m', COALESCE(registered_at, created_at)) AS m, COUNT(*) AS c
                          FROM opportunities WHERE user_id = :u
                          AND status IN ('registered','submitted','shortlisted','won','rejected')
                          GROUP BY m)""",
    "team_player": "SELECT COUNT(*) >= 1 FROM team_members WHERE user_id = :u AND status = 'active'",
    "scribe": "SELECT COUNT(*) >= 3 FROM journal_entries WHERE user_id = :u",
    "planner": """SELECT COUNT(*) >= 1 FROM opportunities o WHERE o.user_id = :u
                  AND EXISTS (SELECT 1 FROM milestones m WHERE m.opportunity_id = o.id)
                  AND NOT EXISTS (SELECT 1 FROM milestones m WHERE m.opportunity_id = o.id AND m.done = 0)""",
    "trophy_hunter": "SELECT COUNT(*) >= 1 FROM opportunities WHERE user_id = :u AND trophy_claimed = 1",
    "side_quester": "SELECT COUNT(*) >= 1 FROM feed_posts WHERE user_id = :u",
    "collector": "SELECT COUNT(*) >= 5 FROM assets WHERE user_id = :u",
}


def check_badges(db, user_id, today=None):
    """Unlock any badge whose SQL rule now holds; returns the newly unlocked badge names. # CO3"""
    owned = {r["code"] for r in db.execute(
        "SELECT b.code FROM user_badges ub JOIN badges b ON b.id = ub.badge_id WHERE ub.user_id = ?", (user_id,))}
    new = []
    for code, sql in BADGE_RULES.items():
        if code in owned:
            continue
        try:
            if db.execute(sql, {"u": user_id}).fetchone()[0]:
                new.append(code)
        except Exception:  # a broken rule must never break the request
            log.exception("badge rule %s failed", code)
    if "streak_7" not in owned and current_streak(active_days(db, user_id), today) >= 7:
        new.append("streak_7")
    names = []
    for code in new:
        badge = db.execute("SELECT id, name FROM badges WHERE code = ?", (code,)).fetchone()
        if not badge:
            continue
        db.execute("INSERT OR IGNORE INTO user_badges (user_id, badge_id) VALUES (?, ?)", (user_id, badge["id"]))
        db.execute("INSERT OR IGNORE INTO notifications (user_id, kind, message, link, dedupe_key) VALUES (?,?,?,?,?)",
                   (user_id, "badge", f"Badge unlocked: {badge['name']}!", "/badges", f"badge-{code}"))
        names.append(badge["name"])
    db.commit()
    return names
