"""Landing, deadline dashboard, Quest Map, insights, clashes, notifications and calendar."""
from flask import Blueprint, Response, flash, g, jsonify, redirect, render_template, request, url_for

from ..constants import MODES, STATUSES, TYPES
from ..db import get_db
from ..models import Opportunity
from ..security import login_required
from ..services import clash, game, ics, insights as insights_service, questmap, sample, scoring
from ..services.eligibility import check as check_eligibility
from ..services.notify import scan_reminders
from .common import apply_filters

bp = Blueprint("main", __name__)


@bp.route("/")
def landing():
    return render_template("landing.html")


@bp.route("/dashboard")
@login_required
def dashboard():
    """Deadline dashboard: urgency buckets, filters, top-5 and clash summary. # CO3 web"""
    db = get_db()
    scan_reminders(db, user_id=g.user.id)  # cheap; keeps reminders working even without the scheduler
    all_opps = Opportunity.for_user(db, g.user.id)
    fits = game.user_fits(db, g.user)
    opps = apply_filters(all_opps, request.args, fits)
    top = scoring.top_n(all_opps, fits, 5)
    buckets = {"overdue": [], "urgent": [], "week": [], "later": [], "done": []}
    for o in opps:
        buckets[o.urgency()].append(o)
    clashes = clash.detect_clashes(game.calendar_events(db, g.user))
    stats = db.execute(
        "SELECT COUNT(*) total, SUM(status IN ('interested','preparing','registered')) open, "
        "SUM(status = 'won') won, SUM(status IN ('submitted','shortlisted','won')) submitted "
        "FROM opportunities WHERE user_id = ?", (g.user.id,)).fetchone()
    return render_template("dashboard.html", buckets=buckets, top=top, fits=fits, clashes=clashes[:2],
                           stats=stats, args=request.args, types=TYPES, statuses=STATUSES, modes=MODES,
                           filtered=bool(set(request.args) & {"q", "type", "status", "mode", "range"}),
                           total=len(all_opps), breakdown=scoring.breakdown_text)


@bp.route("/map")
@login_required
def world_map():
    db = get_db()
    pins = game.world_map_pins(db, g.user)
    layout = questmap.build_layout(pins, seed=g.user.id * 31 + len(pins))
    return render_template("map.html", layout=layout, mode="world", avatar_at=questmap.avatar_index(pins),
                           map_key=f"world-{g.user.id}", opp=None, trophy_ready=False)


@bp.route("/insights")
@login_required
def insights():
    data = insights_service.build_insights(get_db(), g.user.id)
    heat = insights_service.heatmap(get_db(), g.user.id)
    return render_template("insights.html", data=data, heat=heat)


@bp.route("/insights/chart/<name>.png")
@login_required
def insights_chart(name):
    if name not in ("types", "success", "monthly"):
        return ("", 404)
    data = insights_service.build_insights(get_db(), g.user.id)
    return Response(insights_service.chart_png(data, name), mimetype="image/png",
                    headers={"Cache-Control": "no-store"})


@bp.route("/insights.json")
@login_required
def insights_json():
    return jsonify(insights_service.build_insights(get_db(), g.user.id))


@bp.route("/clashes")
@login_required
def clashes():
    db = get_db()
    events = game.calendar_events(db, g.user)
    return render_template("clashes.html", clashes=clash.detect_clashes(events), load=clash.weekly_load(events))


@bp.route("/eligibility")
@login_required
def eligibility():
    opps = [o for o in Opportunity.for_user(get_db(), g.user.id) if o.is_open]
    rows = [(o, *check_eligibility(g.user, o)) for o in opps]
    return render_template("eligibility.html", rows=rows)


@bp.route("/notifications")
@login_required
def notifications():
    rows = get_db().execute("SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 100",
                            (g.user.id,)).fetchall()
    return render_template("notifications.html", rows=rows)


@bp.route("/notifications.json")
@login_required
def notifications_json():
    rows = get_db().execute("SELECT id, kind, message, link, is_read, created_at FROM notifications WHERE user_id = ? "
                            "ORDER BY created_at DESC, id DESC LIMIT 8", (g.user.id,)).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/notifications/read", methods=["POST"])
@login_required
def notifications_read():
    db = get_db()
    db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (g.user.id,))
    db.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(ok=True)
    flash("All notifications marked as read.", "success")
    return redirect(url_for("main.notifications"))


@bp.route("/notifications/clear", methods=["POST"])
@login_required
def notifications_clear():
    db = get_db()
    db.execute("DELETE FROM notifications WHERE user_id = ? AND is_read = 1", (g.user.id,))
    db.commit()
    flash("Read notifications cleared.", "success")
    return redirect(url_for("main.notifications"))


@bp.route("/load-sample", methods=["POST"])
@login_required
def load_sample():
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM opportunities WHERE user_id = ? AND source = 'sample'", (g.user.id,)).fetchone()[0]:
        flash("Sample quests are already loaded.", "info")
    else:
        count = sample.load_sample(db, g.user.id, history_xp=False)
        flash(f"Loaded {count} sample quests. Explore the map!", "success")
    return redirect(url_for("main.dashboard"))


@bp.route("/calendar.ics")
@login_required
def calendar_all():
    db = get_db()
    events = []
    for o in Opportunity.for_user(db, g.user.id):
        if o.status in ("won", "rejected"):
            continue
        events += ics.quest_events(o, o.rounds(db), o.milestones(db))
    return Response(ics.build_ics(events, f"{g.user.name}'s HackTrack quests"), mimetype="text/calendar",
                    headers={"Content-Disposition": "attachment; filename=hacktrack.ics"})
