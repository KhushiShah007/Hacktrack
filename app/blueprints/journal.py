"""Training Log: post-mortem journal with full-text search and tag filtering."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..db import get_db
from ..models import Opportunity
from ..security import login_required
from ..services import game
from ..utils import csv_list

bp = Blueprint("journal", __name__, url_prefix="/training-log")


@bp.route("/")
@login_required
def index():
    db = get_db()
    q = request.args.get("q", "").strip()
    tag = request.args.get("tag", "").strip().lower()
    sql = ("SELECT j.*, o.title AS quest_title, o.status AS quest_status FROM journal_entries j "
           "LEFT JOIN opportunities o ON o.id = j.opportunity_id WHERE j.user_id = ?")
    args = [g.user.id]
    if q:
        like = f"%{q}%"
        sql += " AND (j.title LIKE ? OR j.what_worked LIKE ? OR j.what_failed LIKE ? OR j.lessons LIKE ? OR j.tags LIKE ?)"
        args += [like] * 5
    if tag:
        sql += " AND (',' || lower(replace(j.tags, ' ', '')) || ',') LIKE ?"
        args.append(f"%,{tag},%")
    entries = db.execute(sql + " ORDER BY j.created_at DESC", args).fetchall()
    all_tags = sorted({t.lower() for r in db.execute("SELECT tags FROM journal_entries WHERE user_id = ?", (g.user.id,))
                       for t in csv_list(r["tags"])})
    avg = db.execute("SELECT ROUND(AVG(rating), 1) FROM journal_entries WHERE user_id = ?", (g.user.id,)).fetchone()[0]
    return render_template("journal/index.html", entries=entries, q=q, tag=tag, all_tags=all_tags, avg=avg)


def _entry_or_404(entry_id):
    row = get_db().execute("SELECT * FROM journal_entries WHERE id = ? AND user_id = ?", (entry_id, g.user.id)).fetchone()
    if not row:
        abort(404)
    return row


def _validate(form):
    errors = {}
    if not 2 <= len(form.get("title", "").strip()) <= 120:
        errors["title"] = "Give the entry a title (2-120 characters)."
    rating = form.get("rating", "3")
    if not (rating.isdigit() and 1 <= int(rating) <= 5):
        errors["rating"] = "Rating is 1 to 5 stars."
    return errors


@bp.route("/new", methods=["GET", "POST"])
@bp.route("/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def edit(entry_id=None):
    db = get_db()
    entry = _entry_or_404(entry_id) if entry_id else None
    quests = Opportunity.for_user(db, g.user.id, order="deadline DESC")
    errors = {}
    form = request.form if request.method == "POST" else (dict(entry) if entry else {"opportunity_id": request.args.get("quest", type=int)})
    if request.method == "POST":
        errors = _validate(request.form)
        opp_id = request.form.get("opportunity_id", type=int)
        if opp_id and not Opportunity.get(db, opp_id, g.user.id):
            opp_id = None
        if not errors:
            values = (opp_id, request.form["title"].strip(), request.form.get("what_worked", "").strip()[:2000],
                      request.form.get("what_failed", "").strip()[:2000], request.form.get("lessons", "").strip()[:2000],
                      int(request.form.get("rating", 3)),
                      ",".join(t.strip().lower() for t in request.form.get("tags", "").split(",") if t.strip()))
            if entry:
                db.execute("UPDATE journal_entries SET opportunity_id=?, title=?, what_worked=?, what_failed=?, lessons=?, "
                           "rating=?, tags=? WHERE id = ? AND user_id = ?", (*values, entry["id"], g.user.id))
                db.commit()
                flash("Training Log entry updated.", "success")
            else:
                db.execute("INSERT INTO journal_entries (opportunity_id, title, what_worked, what_failed, lessons, rating, tags, user_id) "
                           "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (*values, g.user.id))
                db.commit()
                game.reward("journal", opp_id or "")
                flash("Lesson logged. Wisdom +1!", "success")
            return redirect(url_for("journal.index"))
    return render_template("journal/form.html", entry=entry, form=form, errors=errors, quests=quests)


@bp.route("/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete(entry_id):
    entry = _entry_or_404(entry_id)
    db = get_db()
    db.execute("DELETE FROM journal_entries WHERE id = ?", (entry["id"],))
    db.commit()
    flash("Entry deleted.", "success")
    return redirect(url_for("journal.index"))
