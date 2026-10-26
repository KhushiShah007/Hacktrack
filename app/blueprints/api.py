"""Read-only REST API with bearer-token auth (used by the Tkinter desktop widget)."""
from flask import Blueprint, g, jsonify, request

from ..db import get_db
from ..models import Opportunity
from ..security import token_required
from ..services import xp as xp_service
from ..utils import days_left

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/health")
def health():
    return jsonify(ok=True, app="HackTrack")


@bp.route("/opportunities")
@token_required
def opportunities():
    """GET /api/opportunities?upcoming=1&limit=5&type=hackathon  # CO3 REST"""
    db = get_db()
    opps = Opportunity.for_user(db, g.api_user_id)
    if request.args.get("upcoming") == "1":
        opps = [o for o in opps if o.is_open and (days_left(o.deadline) or -1) >= 0]
    qtype = request.args.get("type")
    if qtype:
        opps = [o for o in opps if o.type == qtype]
    limit = min(max(request.args.get("limit", 100, type=int), 1), 500)
    return jsonify(count=len(opps[:limit]), opportunities=[o.to_dict() for o in opps[:limit]])


@bp.route("/stats")
@token_required
def stats():
    db = get_db()
    uid = g.api_user_id
    rows = db.execute("SELECT status, COUNT(*) AS n FROM opportunities WHERE user_id = ? GROUP BY status", (uid,)).fetchall()
    by_type = db.execute("SELECT type, COUNT(*) AS n, SUM(status = 'won') AS won FROM opportunities "
                         "WHERE user_id = ? GROUP BY type ORDER BY n DESC", (uid,)).fetchall()
    total = xp_service.total_xp(db, uid)
    user = db.execute("SELECT username, display_name FROM users WHERE id = ?", (uid,)).fetchone()
    return jsonify(
        player=user["display_name"] or user["username"],
        by_status={r["status"]: r["n"] for r in rows},
        by_type=[dict(r) for r in by_type],
        xp=xp_service.progress(total),
        streak=xp_service.current_streak(xp_service.active_days(db, uid)),
    )
