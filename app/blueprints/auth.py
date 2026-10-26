"""Signup / login / logout, 'Create your player' onboarding and settings."""
import re
import sqlite3

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..constants import AVATAR_LOOKS, BRANCHES
from ..db import get_db, query, skill_id
from ..models import User
from ..security import login_required, new_token, safe_next

bp = Blueprint("auth", __name__)
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def login_user(user_id):
    session.clear()
    session["user_id"] = user_id
    session.permanent = True


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    errors, form = {}, request.form
    if request.method == "POST":
        username = form.get("username", "").strip()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        if not USERNAME_RE.match(username):
            errors["username"] = "3-30 letters, numbers or underscores."
        if not EMAIL_RE.match(email):
            errors["email"] = "Enter a valid email address."
        if len(password) < 8:
            errors["password"] = "Use at least 8 characters."
        if password != form.get("confirm", ""):
            errors["confirm"] = "Passwords don't match."
        if not errors:
            db = get_db()
            try:
                cur = db.execute(
                    "INSERT INTO users (username, email, password_hash, display_name, api_token) VALUES (?, ?, ?, ?, ?)",
                    (username, email, generate_password_hash(password), username, new_token()))
                db.commit()
            except sqlite3.IntegrityError:
                errors["username"] = "That username or email is already taken."
            else:
                login_user(cur.lastrowid)
                flash("Player created! Now design your character.", "success")
                return redirect(url_for("auth.onboarding"))
    return render_template("auth/signup.html", errors=errors, form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        ident = request.form.get("username", "").strip()
        row = query("SELECT * FROM users WHERE username = ? OR email = ?", (ident, ident.lower()), one=True)
        if row is None or not check_password_hash(row["password_hash"], request.form.get("password", "")):
            error = "Wrong username or password. Try again, player."
        else:
            login_user(row["id"])
            flash(f"Welcome back, {row['display_name'] or row['username']}!", "success")
            if not row["onboarded"]:
                return redirect(url_for("auth.onboarding"))
            return redirect(safe_next(request.args.get("next")) or url_for("main.dashboard"))
    return render_template("auth/login.html", error=error)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Game saved. See you next time!", "info")
    return redirect(url_for("main.landing"))


def _save_profile(form, db, errors):
    year = form.get("year", "").strip()
    if year and not (year.isdigit() and 1 <= int(year) <= 6):
        errors["year"] = "Year must be 1 to 6."
    look = form.get("avatar_look", "knight")
    if look not in AVATAR_LOOKS:
        errors["avatar_look"] = "Pick one of the four looks."
    name = form.get("display_name", "").strip()
    if not 1 <= len(name) <= 40:
        errors["display_name"] = "Name needs 1-40 characters."
    if errors:
        return False
    db.execute(
        "UPDATE users SET display_name=?, avatar_look=?, college=?, year=?, branch=?, interests=?, bio=?, onboarded=1 "
        "WHERE id = ?",
        (name, look, form.get("college", "").strip()[:120], int(year) if year else None,
         form.get("branch", "").strip()[:40], form.get("interests", "").strip()[:300],
         form.get("bio", g.user.bio).strip()[:500], g.user.id))
    _save_user_skills(db, form)
    db.commit()
    return True


def _save_user_skills(db, form):
    db.execute("DELETE FROM user_skills WHERE user_id = ?", (g.user.id,))
    for key, value in form.items():
        if key.startswith("skill__") and value.isdigit() and 1 <= int(value) <= 5:
            db.execute("INSERT INTO user_skills (user_id, skill_id, proficiency) VALUES (?, ?, ?)",
                       (g.user.id, skill_id(key[7:], db), int(value)))
    for name in (n.strip()[:40] for n in form.get("extra_skills", "").split(",")):
        if name:
            db.execute("INSERT OR IGNORE INTO user_skills (user_id, skill_id, proficiency) VALUES (?, ?, 3)",
                       (g.user.id, skill_id(name, db)))


def _skill_context():
    db = get_db()
    catalog = [r["name"] for r in db.execute(
        "SELECT name FROM skills WHERE id IN (SELECT MIN(id) FROM skills GROUP BY lower(name)) ORDER BY category, name")]
    return {"catalog": catalog, "mine": User(id=g.user.id).skills(db)}


@bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    errors = {}
    if request.method == "POST":
        if _save_profile(request.form, get_db(), errors):
            flash("Character saved. Your adventure begins!", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("auth/onboarding.html", errors=errors, looks=AVATAR_LOOKS, branches=BRANCHES,
                           **_skill_context())


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    errors = {}
    db = get_db()
    if request.method == "POST":
        if _save_profile(request.form, db, errors):
            db.execute("UPDATE users SET is_public=?, telegram_chat_id=?, email_reminders=? WHERE id=?",
                       (1 if request.form.get("is_public") else 0, request.form.get("telegram_chat_id", "").strip()[:40],
                        1 if request.form.get("email_reminders") else 0, g.user.id))
            db.commit()
            flash("Settings saved.", "success")
            return redirect(url_for("auth.settings"))
        flash("Some fields need fixing.", "error")
    return render_template("auth/settings.html", errors=errors, looks=AVATAR_LOOKS, branches=BRANCHES,
                           **_skill_context())


@bp.route("/settings/token", methods=["POST"])
@login_required
def regenerate_token():
    db = get_db()
    db.execute("UPDATE users SET api_token = ? WHERE id = ?", (new_token(), g.user.id))
    db.commit()
    flash("New API token generated. Update widget_config.json for the desktop widget.", "success")
    return redirect(url_for("auth.settings") + "#api")


@bp.route("/settings/password", methods=["POST"])
@login_required
def change_password():
    db = get_db()
    row = db.execute("SELECT password_hash FROM users WHERE id = ?", (g.user.id,)).fetchone()
    new = request.form.get("new_password", "")
    if not check_password_hash(row["password_hash"], request.form.get("current_password", "")):
        flash("Current password is wrong.", "error")
    elif len(new) < 8:
        flash("New password needs at least 8 characters.", "error")
    else:
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new), g.user.id))
        db.commit()
        flash("Password changed.", "success")
    return redirect(url_for("auth.settings") + "#security")
