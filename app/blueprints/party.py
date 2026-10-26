"""Party (shared team board): teams, invites, tasks per round, activity log, team skill-match."""
from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for

from ..constants import TASK_STATUSES
from ..db import get_db
from ..models import Opportunity, Team, User
from ..security import login_required
from ..services import game, skillmatch
from ..utils import fmt_dt, parse_dt
from .common import wants_json

bp = Blueprint("party", __name__, url_prefix="/party")


def _log(db, team_id, message):
    db.execute("INSERT INTO team_log (team_id, user_id, message) VALUES (?, ?, ?)", (team_id, g.user.id, message[:300]))


def _team_or_404(team_id, require_active=True):
    db = get_db()
    row = db.execute("SELECT t.*, tm.status AS my_status FROM teams t JOIN team_members tm ON tm.team_id = t.id "
                     "WHERE t.id = ? AND tm.user_id = ?", (team_id, g.user.id)).fetchone()
    if not row or (require_active and row["my_status"] != "active"):
        abort(404)
    team = Team.from_row(row)
    team.load_members(db)
    return team


@bp.route("/")
@login_required
def index():
    db = get_db()
    teams = db.execute(
        "SELECT t.*, tm.status AS my_status, o.title AS quest_title, "
        "(SELECT COUNT(*) FROM team_members x WHERE x.team_id = t.id AND x.status = 'active') AS members, "
        "(SELECT COUNT(*) FROM tasks k WHERE k.team_id = t.id AND k.status != 'done') AS open_tasks "
        "FROM teams t JOIN team_members tm ON tm.team_id = t.id LEFT JOIN opportunities o ON o.id = t.opportunity_id "
        "WHERE tm.user_id = ? ORDER BY tm.status DESC, t.created_at DESC", (g.user.id,)).fetchall()
    quests = Opportunity.for_user(db, g.user.id, "AND status NOT IN ('won','rejected')")
    return render_template("party/index.html", teams=teams, quests=quests)


@bp.route("/new", methods=["POST"])
@login_required
def create():
    name = request.form.get("name", "").strip()
    if not 2 <= len(name) <= 60:
        flash("Party name needs 2-60 characters.", "error")
        return redirect(url_for("party.index"))
    db = get_db()
    opp_id = request.form.get("opportunity_id", type=int)
    if opp_id and not Opportunity.get(db, opp_id, g.user.id):
        opp_id = None
    cur = db.execute("INSERT INTO teams (name, owner_id, opportunity_id) VALUES (?, ?, ?)", (name, g.user.id, opp_id))
    db.execute("INSERT INTO team_members (team_id, user_id, role, status) VALUES (?, ?, 'leader', 'active')",
               (cur.lastrowid, g.user.id))
    _log(db, cur.lastrowid, f"{g.user.name} formed the party")
    db.commit()
    game.reward("join_party", cur.lastrowid, once=True)
    flash(f"Party '{name}' formed! Invite teammates by username.", "success")
    return redirect(url_for("party.detail", team_id=cur.lastrowid))


@bp.route("/<int:team_id>")
@login_required
def detail(team_id):
    db = get_db()
    team = _team_or_404(team_id, require_active=False)
    if any(m.user_id == g.user.id and m.status == "invited" for m in team.members):
        return render_template("party/invite.html", team=team)
    tasks = db.execute(
        "SELECT k.*, u.username AS assignee, u.display_name AS assignee_name, u.avatar_look, r.name AS round_name "
        "FROM tasks k LEFT JOIN users u ON u.id = k.assignee_id LEFT JOIN rounds r ON r.id = k.round_id "
        "WHERE k.team_id = ? ORDER BY k.due_date IS NULL, k.due_date, k.id", (team.id,)).fetchall()
    columns = {s: [t for t in tasks if t["status"] == s] for s in TASK_STATUSES}
    log = db.execute("SELECT l.*, u.username FROM team_log l LEFT JOIN users u ON u.id = l.user_id "
                     "WHERE l.team_id = ? ORDER BY l.id DESC LIMIT 30", (team.id,)).fetchall()
    quest = rounds = match = None
    if team.opportunity_id:
        owner_quest = db.execute("SELECT * FROM opportunities WHERE id = ?", (team.opportunity_id,)).fetchone()
        if owner_quest:
            quest = Opportunity.from_row(owner_quest)
            rounds = quest.rounds(db)
            required = quest.required_skills(db)
            match = skillmatch.team_fit(required, {m.name: m.skills for m in team.active_members})
    return render_template("party/detail.html", team=team, columns=columns, log=log, quest=quest, rounds=rounds or [],
                           match=match, statuses=TASK_STATUSES)


@bp.route("/<int:team_id>/invite", methods=["POST"])
@login_required
def invite(team_id):
    team = _team_or_404(team_id)
    db = get_db()
    username = request.form.get("username", "").strip()
    user = User.by_username(db, username)
    if not user:
        flash(f"No player called '{username}'.", "error")
    elif any(m.user_id == user.id for m in team.members):
        flash(f"{user.username} is already in this party.", "info")
    else:
        db.execute("INSERT INTO team_members (team_id, user_id, role, status) VALUES (?, ?, 'member', 'invited')",
                   (team.id, user.id))
        db.execute("INSERT OR IGNORE INTO notifications (user_id, kind, message, link, dedupe_key) VALUES (?, 'party', ?, ?, ?)",
                   (user.id, f"{g.user.name} invited you to the party '{team.name}'.", f"/party/{team.id}",
                    f"invite-{team.id}-{user.id}"))
        _log(db, team.id, f"{g.user.name} invited {user.username}")
        db.commit()
        flash(f"Invite sent to {user.username}.", "success")
    return redirect(url_for("party.detail", team_id=team.id))


@bp.route("/<int:team_id>/respond", methods=["POST"])
@login_required
def respond(team_id):
    team = _team_or_404(team_id, require_active=False)
    db = get_db()
    if request.form.get("accept") == "1":
        db.execute("UPDATE team_members SET status = 'active', joined_at = datetime('now','localtime') "
                   "WHERE team_id = ? AND user_id = ?", (team.id, g.user.id))
        _log(db, team.id, f"{g.user.name} joined the party")
        db.commit()
        game.reward("join_party", team.id, once=True)
        flash(f"You joined {team.name}!", "success")
        return redirect(url_for("party.detail", team_id=team.id))
    db.execute("DELETE FROM team_members WHERE team_id = ? AND user_id = ?", (team.id, g.user.id))
    db.commit()
    flash("Invite declined.", "info")
    return redirect(url_for("party.index"))


@bp.route("/<int:team_id>/leave", methods=["POST"])
@login_required
def leave(team_id):
    team = _team_or_404(team_id)
    db = get_db()
    if team.owner_id == g.user.id:
        db.execute("DELETE FROM teams WHERE id = ?", (team.id,))
        flash(f"Party '{team.name}' disbanded.", "success")
    else:
        db.execute("DELETE FROM team_members WHERE team_id = ? AND user_id = ?", (team.id, g.user.id))
        _log(db, team.id, f"{g.user.name} left the party")
        flash(f"You left {team.name}.", "success")
    db.commit()
    return redirect(url_for("party.index"))


@bp.route("/<int:team_id>/tasks", methods=["POST"])
@login_required
def add_task(team_id):
    team = _team_or_404(team_id)
    db = get_db()
    title = request.form.get("title", "").strip()[:160]
    if not title:
        flash("Task needs a title.", "error")
        return redirect(url_for("party.detail", team_id=team.id))
    assignee = request.form.get("assignee_id", type=int)
    if assignee and assignee not in {m.user_id for m in team.active_members}:
        assignee = None
    round_id = request.form.get("round_id", type=int)
    if round_id and not db.execute("SELECT 1 FROM rounds WHERE id = ? AND opportunity_id = ?",
                                   (round_id, team.opportunity_id)).fetchone():
        round_id = None
    due = parse_dt(request.form.get("due_date"))
    db.execute("INSERT INTO tasks (team_id, round_id, assignee_id, title, due_date, created_by) VALUES (?, ?, ?, ?, ?, ?)",
               (team.id, round_id, assignee, title, fmt_dt(due) if due else None, g.user.id))
    _log(db, team.id, f"{g.user.name} added task '{title}'")
    db.commit()
    flash("Task added to the board.", "success")
    return redirect(url_for("party.detail", team_id=team.id))


def _task_or_404(task_id):
    row = get_db().execute(
        "SELECT k.* FROM tasks k JOIN team_members tm ON tm.team_id = k.team_id "
        "WHERE k.id = ? AND tm.user_id = ? AND tm.status = 'active'", (task_id, g.user.id)).fetchone()
    if not row:
        abort(404)
    return row


@bp.route("/tasks/<int:task_id>/move", methods=["POST"])
@login_required
def move_task(task_id):
    task = _task_or_404(task_id)
    status = (request.get_json(silent=True) or {}).get("status") or request.form.get("status")
    if status not in TASK_STATUSES:
        abort(400)
    db = get_db()
    db.execute("UPDATE tasks SET status = ?, updated_at = datetime('now','localtime') WHERE id = ?", (status, task["id"]))
    _log(db, task["team_id"], f"{g.user.name} moved '{task['title']}' to {status}")
    db.commit()
    if wants_json():
        return jsonify(ok=True, status=status)
    return redirect(url_for("party.detail", team_id=task["team_id"]))


@bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    task = _task_or_404(task_id)
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task["id"],))
    _log(db, task["team_id"], f"{g.user.name} deleted task '{task['title']}'")
    db.commit()
    flash("Task deleted.", "success")
    return redirect(url_for("party.detail", team_id=task["team_id"]))
