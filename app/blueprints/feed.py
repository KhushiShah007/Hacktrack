"""Side Quests: a college opportunity feed with upvotes and 'Add to my quests'."""
from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for

from ..constants import TYPES
from ..db import get_db
from ..models import Opportunity
from ..security import login_required
from ..services import game
from ..utils import fmt_dt, parse_dt
from .common import URL_OK, wants_json

bp = Blueprint("feed", __name__, url_prefix="/side-quests")


@bp.route("/")
@login_required
def index():
    db = get_db()
    qtype = request.args.get("type", "")
    scope = request.args.get("scope", "college" if g.user.college else "all")
    sort = request.args.get("sort", "top")
    where, args = ["p.deadline >= datetime('now','localtime','-1 day')"], []
    if qtype in TYPES:
        where.append("p.type = ?")
        args.append(qtype)
    if scope == "college" and g.user.college:
        where.append("p.college = ?")
        args.append(g.user.college)
    order = "votes DESC, p.created_at DESC" if sort == "top" else "p.created_at DESC"
    posts = db.execute(
        f"SELECT p.*, u.username, u.display_name, u.avatar_look, "
        f"(SELECT COUNT(*) FROM feed_votes v WHERE v.post_id = p.id) AS votes, "
        f"EXISTS(SELECT 1 FROM feed_votes v WHERE v.post_id = p.id AND v.user_id = ?) AS voted, "
        f"EXISTS(SELECT 1 FROM opportunities o WHERE o.user_id = ? AND o.title = p.title) AS adopted "
        f"FROM feed_posts p JOIN users u ON u.id = p.user_id WHERE {' AND '.join(where)} ORDER BY {order} LIMIT 100",
        (g.user.id, g.user.id, *args)).fetchall()
    return render_template("feed/index.html", posts=posts, types=TYPES, args=request.args, scope=scope, sort=sort)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    errors, form = {}, request.form
    if request.method == "POST":
        title = form.get("title", "").strip()
        qtype = form.get("type", "")
        deadline = parse_dt(form.get("deadline"))
        link = form.get("link", "").strip()
        if not 2 <= len(title) <= 160:
            errors["title"] = "Title needs 2-160 characters."
        if qtype not in TYPES:
            errors["type"] = "Pick a type."
        if not deadline:
            errors["deadline"] = "Add the deadline."
        if link and not URL_OK.match(link):
            errors["link"] = "Links must start with http(s)://"
        if not errors:
            db = get_db()
            db.execute("INSERT INTO feed_posts (user_id, college, type, title, description, link, deadline, prize_text, tags) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (g.user.id, g.user.college, qtype, title, form.get("description", "").strip()[:1500], link,
                        fmt_dt(deadline), form.get("prize_text", "").strip()[:80], form.get("tags", "").strip()[:200]))
            db.commit()
            game.reward("feed_post")
            flash("Side Quest posted for your college!", "success")
            return redirect(url_for("feed.index"))
    return render_template("feed/form.html", errors=errors, form=form, types=TYPES)


def _post_or_404(post_id):
    row = get_db().execute("SELECT * FROM feed_posts WHERE id = ?", (post_id,)).fetchone()
    if not row:
        abort(404)
    return row


@bp.route("/<int:post_id>/vote", methods=["POST"])
@login_required
def vote(post_id):
    post = _post_or_404(post_id)
    db = get_db()
    if db.execute("SELECT 1 FROM feed_votes WHERE post_id = ? AND user_id = ?", (post["id"], g.user.id)).fetchone():
        db.execute("DELETE FROM feed_votes WHERE post_id = ? AND user_id = ?", (post["id"], g.user.id))
        voted = False
    else:
        db.execute("INSERT INTO feed_votes (post_id, user_id) VALUES (?, ?)", (post["id"], g.user.id))
        voted = True
    db.commit()
    votes = db.execute("SELECT COUNT(*) FROM feed_votes WHERE post_id = ?", (post["id"],)).fetchone()[0]
    if wants_json():
        return jsonify(ok=True, voted=voted, votes=votes)
    return redirect(request.referrer or url_for("feed.index"))


@bp.route("/<int:post_id>/adopt", methods=["POST"])
@login_required
def adopt(post_id):
    post = _post_or_404(post_id)
    db = get_db()
    opp = Opportunity.create(post["type"], user_id=g.user.id, title=post["title"], description=post["description"],
                             link=post["link"], deadline=post["deadline"], prize_text=post["prize_text"],
                             tags=post["tags"], source="side-quest")
    opp.save(db)
    game.reward("add_quest", opp.id)
    flash(f"'{post['title']}' added to your quests.", "success")
    return redirect(url_for("quests.detail", opp_id=opp.id))


@bp.route("/<int:post_id>/delete", methods=["POST"])
@login_required
def delete(post_id):
    post = _post_or_404(post_id)
    if post["user_id"] != g.user.id:
        abort(403)
    db = get_db()
    db.execute("DELETE FROM feed_posts WHERE id = ?", (post["id"],))
    db.commit()
    flash("Side Quest removed.", "success")
    return redirect(url_for("feed.index"))
