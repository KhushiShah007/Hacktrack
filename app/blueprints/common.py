"""Helpers shared by several blueprints: form parsing, filters, status changes."""
import re

from flask import abort, g, request, jsonify, session

from ..constants import MODES, STATUSES, TYPES
from ..db import get_db, skill_id
from ..models import Opportunity
from ..services import game, scoring
from ..utils import fmt_dt, now, parse_dt, days_left

URL_OK = re.compile(r"^https?://[^\s]{3,500}$", re.I)


def wants_json():
    return request.is_json or request.accept_mimetypes.best == "application/json" \
        or request.headers.get("X-Requested-With") == "fetch"


def get_opp_or_404(opp_id):
    opp = Opportunity.get(get_db(), opp_id, g.user.id)
    if opp is None:
        abort(404)
    return opp


def parse_skill_text(text):
    """'Python:3, React' -> {'Python': 3, 'React': 2}"""
    skills = {}
    for part in (text or "").split(","):
        if not part.strip():
            continue
        name, _, imp = part.partition(":")
        name = name.strip()[:40]
        try:
            importance = min(3, max(1, int(imp))) if imp.strip() else 2
        except ValueError:
            importance = 2
        if name:
            skills[name] = importance
    return skills


def skills_to_text(skills):
    return ", ".join(f"{k}:{v}" for k, v in skills.items())


def opp_from_form(form, existing=None):
    """Validate the quest form. Returns (Opportunity, errors dict, skills dict). # CO2 validation"""
    errors = {}
    qtype = form.get("type", "hackathon")
    if qtype not in TYPES:
        errors["type"] = "Pick a quest type."
        qtype = "hackathon"
    title = form.get("title", "").strip()
    if not 2 <= len(title) <= 160:
        errors["title"] = "Title needs 2 to 160 characters."
    deadline = parse_dt(form.get("deadline"))
    if not deadline:
        errors["deadline"] = "Set a valid deadline date."
    status = form.get("status", "interested")
    if status not in STATUSES:
        errors["status"] = "Unknown status."
    mode = form.get("mode", "online")
    if mode not in MODES:
        errors["mode"] = "Mode must be online, offline or hybrid."
    link = form.get("link", "").strip()
    if link and not URL_OK.match(link):
        errors["link"] = "Links must start with http:// or https://"
    nums = {}
    for key, lo, hi, default in (("prize_amount", 0, 1e9, 0), ("team_min", 1, 50, 1), ("team_max", 1, 50, 1),
                                 ("effort_hours", 0, 2000, 0)):
        raw = form.get(key, "").strip()
        try:
            val = float(raw) if raw else default
            if not lo <= val <= hi:
                raise ValueError
            nums[key] = val if key == "prize_amount" else int(val)
        except ValueError:
            errors[key] = f"Enter a number between {lo:g} and {hi:g}."
            nums[key] = default
    if nums["team_max"] < nums["team_min"]:
        errors["team_max"] = "Max team size can't be below the minimum."
    years = ",".join(y for y in re.split(r"[,\s]+", form.get("eligible_years", "")) if y in {"1", "2", "3", "4", "5", "6"})
    cls = Opportunity.class_for(qtype)
    extra = {key: form.get(f"extra_{key}", "").strip()[:200] for key, _ in cls.extra_fields}
    data = dict(
        id=existing.id if existing else None, user_id=g.user.id, title=title,
        organizer=form.get("organizer", "").strip()[:120], description=form.get("description", "").strip()[:4000],
        link=link, tags=",".join(t.strip().lower() for t in form.get("tags", "").split(",") if t.strip())[:300],
        prize_text=form.get("prize_text", "").strip()[:80], mode=mode, location=form.get("location", "").strip()[:120],
        eligible_years=years, eligible_branches=form.get("eligible_branches", "").strip()[:120],
        eligible_colleges=form.get("eligible_colleges", "").strip()[:200],
        eligibility_text=form.get("eligibility_text", "").strip()[:500],
        deadline=fmt_dt(deadline) if deadline else fmt_dt(now()), status=status,
        notes=form.get("notes", "").strip()[:4000], extra=extra,
        source=existing.source if existing else form.get("source", "manual"),
        **nums,
    )
    if existing:
        for keep in ("registered_at", "submitted_at", "result_at", "trophy_claimed", "created_at"):
            data[keep] = getattr(existing, keep)
    opp = Opportunity.create(qtype, **data)
    return opp, errors, parse_skill_text(form.get("skills", ""))


def save_skills(db, opp_id, skills):
    db.execute("DELETE FROM opportunity_skills WHERE opportunity_id = ?", (opp_id,))
    for name, importance in skills.items():
        db.execute("INSERT OR REPLACE INTO opportunity_skills (opportunity_id, skill_id, importance) VALUES (?, ?, ?)",
                   (opp_id, skill_id(name, db), importance))
    db.commit()


STATUS_XP = {"registered": "register", "submitted": "submit", "shortlisted": "shortlist", "won": "win"}
STATUS_TS = {"registered": "registered_at", "submitted": "submitted_at", "shortlisted": "result_at",
             "won": "result_at", "rejected": "result_at"}


def apply_status(opp, new_status):
    """Move a quest to a new pipeline status, stamp timestamps and award XP once. # CO3"""
    db = get_db()
    if new_status not in STATUSES:
        raise ValueError("bad status")
    old = opp.status
    opp.status = new_status
    sets = ["status = ?", "updated_at = datetime('now','localtime')"]
    args = [new_status]
    ts_col = STATUS_TS.get(new_status)
    if ts_col and not getattr(opp, ts_col):
        sets.append(f"{ts_col} = ?")
        args.append(fmt_dt(now()))
    if new_status in ("submitted", "shortlisted", "won") and not opp.registered_at:
        sets.append("registered_at = COALESCE(registered_at, ?)")
        args.append(fmt_dt(now()))
    db.execute(f"UPDATE opportunities SET {', '.join(sets)} WHERE id = ? AND user_id = ?", (*args, opp.id, g.user.id))
    db.commit()
    popups = []
    # moving forward through the pipeline earns every skipped step's XP once
    order = ["registered", "submitted", "shortlisted", "won"]
    if new_status in order:
        for step in order[: order.index(new_status) + 1]:
            if step == "shortlisted" and new_status == "won" and old != "shortlisted":
                continue
            popups += game.reward(STATUS_XP[step], opp.id, once=True)
    return old, popups


def apply_filters(opps, args, fits=None):
    """Search + filters + sort for dashboard and list view. # CO1 lambda/filter/sorted"""
    q = args.get("q", "").strip().lower()
    qtype, status, mode = args.get("type", ""), args.get("status", ""), args.get("mode", "")
    rng = args.get("range", "")
    if q:
        opps = list(filter(lambda o: q in (o.title + " " + o.organizer + " " + o.tags + " " + o.notes).lower(), opps))
    if qtype in TYPES:
        opps = list(filter(lambda o: o.type == qtype, opps))
    if status in STATUSES:
        opps = list(filter(lambda o: o.status == status, opps))
    elif status == "open":
        opps = list(filter(lambda o: o.is_open, opps))
    if mode in MODES:
        opps = list(filter(lambda o: o.mode == mode, opps))
    limits = {"overdue": (-1e9, 0), "48h": (0, 2), "week": (0, 7), "month": (0, 31), "later": (31, 1e9)}
    if rng in limits:
        lo, hi = limits[rng]
        opps = list(filter(lambda o: lo <= (days_left(o.deadline) or 0) < hi, opps))
    sort = args.get("sort", "deadline")
    fits = fits or {}
    keys = {
        "deadline": (lambda o: o.deadline, False),
        "priority": (lambda o: scoring.priority_score(o, fits.get(o.id, 60))[0], True),
        "prize": (lambda o: o.prize_amount, True),
        "title": (lambda o: o.title.lower(), False),
        "created": (lambda o: o.created_at or "", True),
    }
    key, rev = keys.get(sort, keys["deadline"])
    return sorted(opps, key=key, reverse=rev)


def json_ok(**data):
    return jsonify(ok=True, **data)


def pop_popups():
    return session.pop("popups", [])
