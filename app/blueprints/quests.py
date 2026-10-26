"""Quest CRUD, Kanban, rounds, back-plan, inventory, Mission Briefing, import/export, roadmap."""
import mimetypes
import os
import uuid

from flask import (Blueprint, Response, abort, current_app, flash, g, jsonify, redirect, render_template, request,
                   send_from_directory, url_for)
from werkzeug.utils import secure_filename

from ..constants import ASSET_CATEGORIES, MODES, STATUSES, TYPES, ROUND_STATUSES
from ..db import get_db
from ..models import Milestone, Opportunity, Round, User
from ..services import game, ics, io_utils, parser, planner, questmap, scoring, skillmatch
from ..services.eligibility import check as check_eligibility
from ..security import login_required
from ..utils import fmt_dt, now, parse_dt
from .common import (apply_filters, apply_status, get_opp_or_404, json_ok, opp_from_form, save_skills,
                     skills_to_text, wants_json, URL_OK)

bp = Blueprint("quests", __name__, url_prefix="/quests")


# ---------------- list, board, CRUD ----------------
@bp.route("/")
@login_required
def index():
    db = get_db()
    fits = game.user_fits(db, g.user)
    opps = apply_filters(Opportunity.for_user(db, g.user.id), request.args, fits)
    scores = {o.id: scoring.priority_score(o, fits.get(o.id, 60)) for o in opps}
    return render_template("quests/list.html", opps=opps, scores=scores, args=request.args, types=TYPES,
                           statuses=STATUSES, modes=MODES, breakdown=scoring.breakdown_text)


@bp.route("/board")
@login_required
def board():
    opps = apply_filters(Opportunity.for_user(get_db(), g.user.id), request.args)
    columns = {s: [o for o in opps if o.status == s] for s in STATUSES}
    return render_template("quests/board.html", columns=columns, args=request.args, types=TYPES)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        opp, errors, skills = opp_from_form(request.form)
        if not errors:
            db = get_db()
            opp.save(db)
            save_skills(db, opp.id, skills)
            _add_default_rounds(db, opp, request.form.get("auto_rounds") == "1")
            game.reward("add_quest", opp.id)
            if request.form.get("auto_plan") == "1":
                milestones, _ = planner.build_plan(opp.type, opp.deadline, opp.effort_estimate())
                planner.save_plan(db, opp.id, milestones)
            flash(f"Quest accepted: {opp.title}", "success")
            return redirect(url_for("quests.detail", opp_id=opp.id))
        flash("Some fields need fixing before this quest can be saved.", "error")
        return render_template("quests/form.html", opp=opp, errors=errors, skills_text=request.form.get("skills", ""),
                               classes=Opportunity._registry), 400
    qtype = request.args.get("type", "hackathon")
    blank = Opportunity.create(qtype if qtype in TYPES else "hackathon", deadline=fmt_dt(now().replace(hour=23, minute=59)))
    return render_template("quests/form.html", opp=blank, errors={}, skills_text="", classes=Opportunity._registry)


def _add_default_rounds(db, opp, enabled):
    """Optional: create one round per type stage, all due on the quest deadline (user can edit)."""
    if not enabled:
        return
    for seq, name in enumerate(opp.stages(), start=1):
        db.execute("INSERT INTO rounds (opportunity_id, seq, name, deadline) VALUES (?, ?, ?, ?)",
                   (opp.id, seq, name, opp.deadline))
    db.commit()


@bp.route("/<int:opp_id>")
@login_required
def detail(opp_id):
    db = get_db()
    opp = get_opp_or_404(opp_id)
    rounds = opp.rounds(db)
    milestones = opp.milestones(db)
    tree = Milestone.build_tree(milestones)
    required = opp.required_skills(db)
    me = User(id=g.user.id).skills(db)
    fit = skillmatch.fit_score(required, me)
    score, breakdown = scoring.priority_score(opp, fit["score"])
    teams = db.execute("SELECT * FROM teams WHERE opportunity_id = ? AND id IN "
                       "(SELECT team_id FROM team_members WHERE user_id = ? AND status = 'active')",
                       (opp.id, g.user.id)).fetchall()
    team_match = None
    if teams:
        from ..models import Team
        team = Team.from_row(teams[0])
        team.load_members(db)
        team_match = skillmatch.team_fit(required, {m.name: m.skills for m in team.active_members})
        team_match["team"] = team
    assets = db.execute("SELECT * FROM assets WHERE opportunity_id = ? ORDER BY created_at DESC", (opp.id,)).fetchall()
    journal = db.execute("SELECT * FROM journal_entries WHERE opportunity_id = ? AND user_id = ? ORDER BY created_at DESC",
                         (opp.id, g.user.id)).fetchall()
    verdict, reason = check_eligibility(g.user, opp)
    total = len([m for m in milestones if m.parent_id])
    done = len([m for m in milestones if m.parent_id and m.done])
    return render_template("quests/detail.html", opp=opp, rounds=rounds, tree=tree, required=required, fit=fit,
                           score=score, breakdown=breakdown, team_match=team_match, assets=assets, journal=journal,
                           verdict=verdict, reason=reason, plan_progress=round(100 * done / total) if total else 0,
                           plan_total=total, plan_done=done, statuses=STATUSES, round_statuses=ROUND_STATUSES,
                           categories=ASSET_CATEGORIES, breakdown_text=scoring.breakdown_text)


@bp.route("/<int:opp_id>/edit", methods=["GET", "POST"])
@login_required
def edit(opp_id):
    db = get_db()
    existing = get_opp_or_404(opp_id)
    if request.method == "POST":
        opp, errors, skills = opp_from_form(request.form, existing)
        if not errors:
            status_changed = opp.status != existing.status
            opp.status = existing.status
            opp.save(db)
            save_skills(db, opp.id, skills)
            if status_changed:
                apply_status(opp, request.form["status"])
            flash("Quest updated.", "success")
            return redirect(url_for("quests.detail", opp_id=opp.id))
        flash("Some fields need fixing.", "error")
        return render_template("quests/form.html", opp=opp, errors=errors, skills_text=request.form.get("skills", ""),
                               classes=Opportunity._registry), 400
    return render_template("quests/form.html", opp=existing, errors={}, classes=Opportunity._registry,
                           skills_text=skills_to_text(existing.required_skills(db)))


@bp.route("/<int:opp_id>/delete", methods=["POST"])
@login_required
def delete(opp_id):
    db = get_db()
    opp = get_opp_or_404(opp_id)
    for row in db.execute("SELECT stored_name FROM assets WHERE opportunity_id = ? AND kind = 'file'", (opp.id,)).fetchall():
        _remove_file(row["stored_name"])
    db.execute("DELETE FROM opportunities WHERE id = ? AND user_id = ?", (opp.id, g.user.id))
    db.commit()
    flash(f"Quest deleted: {opp.title}", "success")
    return redirect(url_for("quests.index"))


@bp.route("/<int:opp_id>/status", methods=["POST"])
@login_required
def set_status(opp_id):
    opp = get_opp_or_404(opp_id)
    new_status = (request.get_json(silent=True) or {}).get("status") or request.form.get("status")
    if new_status not in STATUSES:
        if wants_json():
            return jsonify(ok=False, error="Unknown status"), 400
        flash("Unknown status.", "error")
        return redirect(request.referrer or url_for("quests.board"))
    old, popups = apply_status(opp, new_status)
    message = f"{opp.title}: {opp.status_label}"
    if new_status in ("won", "rejected", "shortlisted"):
        message += ". Log what you learned in the Training Log!"
    if wants_json():
        from flask import session
        session.pop("popups", None)
        return json_ok(status=new_status, label=opp.status_label, message=message, popups=popups,
                       state=game.quest_state(opp))
    flash(message, "success")
    return redirect(request.referrer or url_for("quests.detail", opp_id=opp.id))


@bp.route("/<int:opp_id>/note", methods=["POST"])
@login_required
def add_note(opp_id):
    opp = get_opp_or_404(opp_id)
    note = request.form.get("note", "").strip()[:1000]
    if not note:
        flash("Write something first.", "error")
    else:
        stamp = now().strftime("%d %b %H:%M")
        notes = (opp.notes + "\n" if opp.notes else "") + f"[{stamp}] {note}"
        db = get_db()
        db.execute("UPDATE opportunities SET notes = ?, updated_at = datetime('now','localtime') WHERE id = ? AND user_id = ?",
                   (notes[-4000:], opp.id, g.user.id))
        db.commit()
        flash("Note added.", "success")
    return redirect(request.referrer or url_for("quests.detail", opp_id=opp.id))


# ---------------- rounds ----------------
@bp.route("/<int:opp_id>/rounds", methods=["POST"])
@login_required
def add_round(opp_id):
    opp = get_opp_or_404(opp_id)
    name = request.form.get("name", "").strip()[:80]
    deadline = parse_dt(request.form.get("deadline"))
    if not name or not deadline:
        flash("A round needs a name and a valid date.", "error")
    else:
        db = get_db()
        seq = db.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM rounds WHERE opportunity_id = ?", (opp.id,)).fetchone()[0]
        db.execute("INSERT INTO rounds (opportunity_id, seq, name, deadline) VALUES (?, ?, ?, ?)",
                   (opp.id, seq, name, fmt_dt(deadline)))
        db.commit()
        flash(f"Round added: {name}", "success")
    return redirect(url_for("quests.detail", opp_id=opp.id) + "#rounds")


def _round_or_404(round_id):
    row = get_db().execute("SELECT r.* FROM rounds r JOIN opportunities o ON o.id = r.opportunity_id "
                           "WHERE r.id = ? AND o.user_id = ?", (round_id, g.user.id)).fetchone()
    if not row:
        abort(404)
    return Round.from_row(row)


@bp.route("/rounds/<int:round_id>/update", methods=["POST"])
@login_required
def update_round(round_id):
    rnd = _round_or_404(round_id)
    data = request.get_json(silent=True) or request.form
    status = data.get("status", rnd.status)
    if status not in ROUND_STATUSES:
        abort(400)
    deadline = parse_dt(data.get("deadline")) or parse_dt(rnd.deadline)
    db = get_db()
    db.execute("UPDATE rounds SET status = ?, result_note = ?, deadline = ? WHERE id = ?",
               (status, (data.get("result_note") if data.get("result_note") is not None else rnd.result_note)[:300],
                fmt_dt(deadline), rnd.id))
    db.commit()
    popups = game.reward("clear_round", rnd.id, once=True) if status == "cleared" else []
    if wants_json():
        from flask import session
        session.pop("popups", None)
        return json_ok(status=status, popups=popups)
    flash(f"Round '{rnd.name}' is now {status}.", "success")
    return redirect(url_for("quests.detail", opp_id=rnd.opportunity_id) + "#rounds")


@bp.route("/rounds/<int:round_id>/delete", methods=["POST"])
@login_required
def delete_round(round_id):
    rnd = _round_or_404(round_id)
    db = get_db()
    db.execute("DELETE FROM rounds WHERE id = ?", (rnd.id,))
    db.commit()
    flash("Round removed.", "success")
    return redirect(url_for("quests.detail", opp_id=rnd.opportunity_id) + "#rounds")


# ---------------- back-planner ----------------
@bp.route("/<int:opp_id>/plan", methods=["POST"])
@login_required
def make_plan(opp_id):
    opp = get_opp_or_404(opp_id)
    try:
        milestones, info = planner.build_plan(opp.type, opp.deadline, opp.effort_estimate())
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("quests.detail", opp_id=opp.id))
    planner.save_plan(get_db(), opp.id, milestones)
    msg = f"Back-plan ready: {len(milestones)} steps from {info['start']}, about {info['hours_per_day']} h/day."
    if info["compressed"]:
        msg += " Deadline is close, so the plan is compressed. Consider extra hours."
    flash(msg, "success")
    return redirect(url_for("quests.detail", opp_id=opp.id) + "#plan")


@bp.route("/<int:opp_id>/plan/clear", methods=["POST"])
@login_required
def clear_plan(opp_id):
    opp = get_opp_or_404(opp_id)
    db = get_db()
    db.execute("DELETE FROM milestones WHERE opportunity_id = ?", (opp.id,))
    db.commit()
    flash("Back-plan cleared.", "success")
    return redirect(url_for("quests.detail", opp_id=opp.id) + "#plan")


@bp.route("/milestones/<int:mid>/toggle", methods=["POST"])
@login_required
def toggle_milestone(mid):
    db = get_db()
    row = db.execute("SELECT m.* FROM milestones m JOIN opportunities o ON o.id = m.opportunity_id "
                     "WHERE m.id = ? AND o.user_id = ?", (mid, g.user.id)).fetchone()
    if not row:
        abort(404)
    done = 0 if row["done"] else 1
    # ticking a phase ticks all its children (recursive CTE)
    db.execute("""WITH RECURSIVE sub(id) AS (SELECT ? UNION ALL SELECT m.id FROM milestones m JOIN sub ON m.parent_id = sub.id)
                  UPDATE milestones SET done = ?, done_at = CASE WHEN ? = 1 THEN datetime('now','localtime') END
                  WHERE id IN (SELECT id FROM sub)""", (mid, done, done))
    if row["parent_id"]:
        # a parent is done when all of its children are done
        db.execute("UPDATE milestones SET done = (SELECT MIN(done) FROM milestones WHERE parent_id = ?) WHERE id = ?",
                   (row["parent_id"], row["parent_id"]))
    db.commit()
    popups = game.reward("finish_milestone", mid, once=True) if done else []
    opp = Opportunity.get(db, row["opportunity_id"], g.user.id)
    ms = opp.milestones(db)
    leaves = [m for m in ms if m.parent_id]
    progress = round(100 * sum(m.done for m in leaves) / len(leaves)) if leaves else 0
    if wants_json():
        from flask import session
        session.pop("popups", None)
        return json_ok(done=done, progress=progress, popups=popups,
                       phases={m.id: m.done for m in ms if not m.parent_id})
    return redirect(request.referrer or url_for("quests.detail", opp_id=opp.id))


# ---------------- quest roadmap + trophy ----------------
@bp.route("/<int:opp_id>/map")
@login_required
def roadmap(opp_id):
    db = get_db()
    opp = get_opp_or_404(opp_id)
    pins = game.roadmap_pins(opp, opp.rounds(db), opp.milestones(db))
    layout = questmap.build_layout(pins, seed=opp.id)
    avatar_at = questmap.avatar_index(pins)
    trophy_ready = bool(pins) and avatar_at == len(pins)
    return render_template("map.html", layout=layout, mode="quest", opp=opp, avatar_at=avatar_at,
                           map_key=f"quest-{opp.id}", trophy_ready=trophy_ready)


@bp.route("/<int:opp_id>/claim-trophy", methods=["POST"])
@login_required
def claim_trophy(opp_id):
    db = get_db()
    opp = get_opp_or_404(opp_id)
    pins = game.roadmap_pins(opp, opp.rounds(db), opp.milestones(db))
    if not pins or questmap.avatar_index(pins) < len(pins):
        return jsonify(ok=False, error="Finish every pin on the road first!"), 400
    first = not opp.trophy_claimed
    db.execute("UPDATE opportunities SET trophy_claimed = 1 WHERE id = ?", (opp.id,))
    db.commit()
    popups = game.reward("trophy", opp.id, once=True)
    from flask import session
    session.pop("popups", None)
    return json_ok(first=first, popups=popups)


# ---------------- inventory (asset vault) ----------------
def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


def _user_dir():
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], str(g.user.id))
    os.makedirs(path, exist_ok=True)
    return path


def _remove_file(stored_name):
    try:
        os.remove(os.path.join(current_app.config["UPLOAD_FOLDER"], stored_name))
    except OSError:
        current_app.logger.warning("could not remove upload %s", stored_name)


@bp.route("/<int:opp_id>/assets", methods=["POST"])
@login_required
def add_asset(opp_id):
    opp = get_opp_or_404(opp_id)
    db = get_db()
    label = request.form.get("label", "").strip()[:80]
    category = request.form.get("category", "other")
    if category not in ASSET_CATEGORIES:
        category = "other"
    upload = request.files.get("file")
    url = request.form.get("url", "").strip()
    if upload and upload.filename:
        filename = secure_filename(upload.filename)
        if not filename or not _allowed(filename):
            flash("That file type isn't allowed. Use PDF, images, PPT/DOC, TXT/MD or ZIP.", "error")
            return redirect(url_for("quests.detail", opp_id=opp.id) + "#inventory")
        stored = f"{g.user.id}/{uuid.uuid4().hex[:12]}_{filename}"
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], stored)
        try:
            _user_dir()
            upload.save(path)
            size = os.path.getsize(path)
        except OSError:
            current_app.logger.exception("upload failed")
            flash("Upload failed. Please try again.", "error")
            return redirect(url_for("quests.detail", opp_id=opp.id) + "#inventory")
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        db.execute("INSERT INTO assets (opportunity_id, user_id, kind, category, label, stored_name, original_name, mime, size_bytes) "
                   "VALUES (?, ?, 'file', ?, ?, ?, ?, ?, ?)",
                   (opp.id, g.user.id, category, label or filename, stored, filename, mime, size))
    elif url:
        if not URL_OK.match(url):
            flash("Links must start with http:// or https://", "error")
            return redirect(url_for("quests.detail", opp_id=opp.id) + "#inventory")
        db.execute("INSERT INTO assets (opportunity_id, user_id, kind, category, label, url) VALUES (?, ?, 'link', ?, ?, ?)",
                   (opp.id, g.user.id, category, label or url[:80], url))
    else:
        flash("Add a link or choose a file.", "error")
        return redirect(url_for("quests.detail", opp_id=opp.id) + "#inventory")
    db.commit()
    game.reward("add_asset")
    flash("Item stored in your Inventory.", "success")
    return redirect(url_for("quests.detail", opp_id=opp.id) + "#inventory")


def _asset_or_404(asset_id):
    row = get_db().execute("SELECT * FROM assets WHERE id = ? AND user_id = ?", (asset_id, g.user.id)).fetchone()
    if not row:
        abort(404)
    return row


@bp.route("/assets/<int:asset_id>/file")
@login_required
def asset_file(asset_id):
    row = _asset_or_404(asset_id)
    if row["kind"] != "file":
        return redirect(row["url"])
    inline = request.args.get("inline") == "1" and (row["mime"].startswith("image/") or row["mime"] == "application/pdf")
    folder, name = os.path.split(row["stored_name"])
    return send_from_directory(os.path.join(current_app.config["UPLOAD_FOLDER"], folder), name,
                               as_attachment=not inline, download_name=row["original_name"], mimetype=row["mime"])


@bp.route("/assets/<int:asset_id>/delete", methods=["POST"])
@login_required
def delete_asset(asset_id):
    row = _asset_or_404(asset_id)
    db = get_db()
    if row["kind"] == "file":
        _remove_file(row["stored_name"])
    db.execute("DELETE FROM assets WHERE id = ?", (row["id"],))
    db.commit()
    flash("Item removed from Inventory.", "success")
    return redirect(url_for("quests.detail", opp_id=row["opportunity_id"]) + "#inventory")


@bp.route("/inventory")
@login_required
def inventory():
    rows = get_db().execute(
        "SELECT a.*, o.title AS quest_title FROM assets a JOIN opportunities o ON o.id = a.opportunity_id "
        "WHERE a.user_id = ? ORDER BY a.created_at DESC", (g.user.id,)).fetchall()
    return render_template("quests/inventory.html", rows=rows)


# ---------------- calendar ----------------
@bp.route("/<int:opp_id>/calendar.ics")
@login_required
def calendar_one(opp_id):
    db = get_db()
    opp = get_opp_or_404(opp_id)
    body = ics.build_ics(ics.quest_events(opp, opp.rounds(db), opp.milestones(db)), opp.title)
    return Response(body, mimetype="text/calendar",
                    headers={"Content-Disposition": f"attachment; filename=quest-{opp.id}.ics"})


# ---------------- Mission Briefing (paste-to-add) ----------------
@bp.route("/briefing", methods=["GET", "POST"])
@login_required
def briefing():
    result, text, score = None, "", None
    if request.method == "POST":
        text = request.form.get("text", "")[:8000]
        if len(text.strip()) < 15:
            flash("Paste a bit more text: a poster caption, WhatsApp forward or email.", "error")
        else:
            result = parser.parse_briefing(text)
            score = parser.confidence_score(result)
    return render_template("quests/briefing.html", result=result, text=text, score=score, types=TYPES, modes=MODES,
                           classes=Opportunity._registry)


@bp.route("/briefing/save", methods=["POST"])
@login_required
def briefing_save():
    opp, errors, skills = opp_from_form(request.form)
    if errors:
        flash("Fix the highlighted fields: " + ", ".join(errors), "error")
        return redirect(url_for("quests.briefing"))
    opp.source = "briefing"
    db = get_db()
    opp.save(db)
    save_skills(db, opp.id, skills)
    names, dates = request.form.getlist("round_name"), request.form.getlist("round_deadline")
    for seq, (name, date) in enumerate(zip(names, dates), start=1):
        dt = parse_dt(date)
        if name.strip() and dt:
            db.execute("INSERT INTO rounds (opportunity_id, seq, name, deadline) VALUES (?, ?, ?, ?)",
                       (opp.id, seq, name.strip()[:80], fmt_dt(dt)))
    db.commit()
    game.reward("add_quest", opp.id)
    flash(f"Mission accepted: {opp.title}", "success")
    return redirect(url_for("quests.detail", opp_id=opp.id))


# ---------------- import / export ----------------
@bp.route("/export.<fmt>")
@login_required
def export(fmt):
    opps = Opportunity.for_user(get_db(), g.user.id)
    if fmt == "csv":
        return Response(io_utils.to_csv(opps), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=hacktrack-quests.csv"})
    if fmt == "json":
        return Response(io_utils.to_json(opps), mimetype="application/json",
                        headers={"Content-Disposition": "attachment; filename=hacktrack-quests.json"})
    abort(404)


@bp.route("/import", methods=["GET", "POST"])
@login_required
def import_view():
    report = None
    if request.method == "POST":
        upload = request.files.get("file")
        if not upload or not upload.filename:
            flash("Choose a .csv or .json file first.", "error")
        else:
            try:
                records = io_utils.parse_upload(secure_filename(upload.filename), upload.read())
                report = io_utils.import_records(get_db(), g.user.id, records)
                level = "success" if not report["errors"] else "info"
                flash(f"Imported {report['created']} of {report['total']} rows.", level)
            except ValueError as exc:
                flash(str(exc), "error")
    return render_template("quests/import.html", report=report, fields=io_utils.EXPORT_FIELDS)
