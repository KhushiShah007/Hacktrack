"""Hall of Fame (public profile), Portfolio Generator and the badge shelf."""
from flask import Blueprint, Response, abort, g, render_template, request, url_for, redirect, flash

from ..db import get_db
from ..models import Badge, Opportunity, User
from ..security import login_required
from ..services import insights as insights_service, portfolio, xp as xp_service

bp = Blueprint("profile", __name__)


def _badges(db, user_id):
    rows = db.execute("SELECT b.*, ub.unlocked_at FROM badges b LEFT JOIN user_badges ub "
                      "ON ub.badge_id = b.id AND ub.user_id = ? ORDER BY ub.unlocked_at IS NULL, ub.unlocked_at, b.id",
                      (user_id,)).fetchall()
    return [Badge.from_row(r) for r in rows]


@bp.route("/u/<username>")
def public(username):
    db = get_db()
    user = User.by_username(db, username)
    if not user:
        abort(404)
    is_me = g.user is not None and g.user.id == user.id
    if not user.is_public and not is_me:
        return render_template("profile/private.html", username=user.username), 403
    opps = Opportunity.for_user(db, user.id, order="deadline DESC")
    results = [o for o in opps if o.status in ("won", "shortlisted", "submitted", "rejected")]
    total = xp_service.total_xp(db, user.id)
    stats = {
        "quests": len(opps),
        "wins": sum(o.status == "won" for o in opps),
        "finals": sum(o.status in ("won", "shortlisted") for o in opps),
        "submitted": sum(o.status in ("submitted", "shortlisted", "won") for o in opps),
        "streak": xp_service.longest_streak(xp_service.active_days(db, user.id)),
    }
    return render_template("profile/public.html", user=user, badges=[b for b in _badges(db, user.id) if b.unlocked],
                           heat=insights_service.heatmap(db, user.id), results=results[:20], stats=stats,
                           progress=xp_service.progress(total), skills=user.skills(db), is_me=is_me,
                           share_url=request.url_root.rstrip("/") + url_for("profile.public", username=user.username))


@bp.route("/u/<username>/privacy", methods=["POST"])
@login_required
def toggle_privacy(username):
    if username.lower() != g.user.username.lower():
        abort(403)
    db = get_db()
    db.execute("UPDATE users SET is_public = 1 - is_public WHERE id = ?", (g.user.id,))
    db.commit()
    flash("Hall of Fame is now " + ("private." if g.user.is_public else "public."), "success")
    return redirect(url_for("profile.public", username=g.user.username))


def _portfolio(db):
    opps = Opportunity.for_user(db, g.user.id)
    skills_by_opp = {o.id: list(o.required_skills(db)) for o in opps}
    lessons = {r["opportunity_id"]: r["lessons"] for r in db.execute(
        "SELECT opportunity_id, lessons FROM journal_entries WHERE user_id = ? AND lessons != '' ORDER BY created_at",
        (g.user.id,))}
    return portfolio.generate(g.user, opps, skills_by_opp, lessons, g.user.skills(db))


@bp.route("/portfolio")
@login_required
def portfolio_view():
    return render_template("profile/portfolio.html", p=_portfolio(get_db()))


@bp.route("/portfolio/download.<fmt>")
@login_required
def portfolio_download(fmt):
    p = _portfolio(get_db())
    if fmt not in ("txt", "md"):
        abort(404)
    return Response(p[fmt], mimetype="text/markdown" if fmt == "md" else "text/plain",
                    headers={"Content-Disposition": f"attachment; filename=hall-of-fame.{fmt}"})


@bp.route("/badges")
@login_required
def badges():
    db = get_db()
    xp_service.check_badges(db, g.user.id)
    shelf = _badges(db, g.user.id)
    db.execute("UPDATE user_badges SET seen = 1 WHERE user_id = ?", (g.user.id,))
    db.commit()
    total = xp_service.total_xp(db, g.user.id)
    events = db.execute("SELECT action, SUM(points) pts, COUNT(*) n FROM xp_events WHERE user_id = ? "
                        "GROUP BY action ORDER BY pts DESC", (g.user.id,)).fetchall()
    return render_template("profile/badges.html", shelf=shelf, progress=xp_service.progress(total), events=events,
                           levels=[(lvl, xp_service.xp_for_level(lvl), xp_service.level_title(lvl)) for lvl in range(1, 17)])
