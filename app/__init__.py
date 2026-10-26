"""HackTrack application factory."""
import json
import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, g, render_template, request, session, jsonify
from flask_wtf.csrf import CSRFProtect, CSRFError

from . import constants, db, sprites
from .models import User
from .utils import pretty_date, countdown, urgency_bucket, parse_dt

csrf = CSRFProtect()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def setup_logging(app):
    """Rotating log file in logs/. # CO2"""
    log_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    handler = RotatingFileHandler(os.path.join(log_dir, "hacktrack.log"), maxBytes=512_000, backupCount=3,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    handler.setLevel(logging.INFO)
    root = logging.getLogger("hacktrack")
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        root.addHandler(handler)
    root.setLevel(logging.INFO)
    app.logger.addHandler(handler)


def create_app(test_config=None):
    app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-me-hacktrack"),
        DATABASE=os.environ.get("HACKTRACK_DB", os.path.join(app.instance_path, "hacktrack.db")),
        UPLOAD_FOLDER=os.path.join(app.instance_path, "uploads"),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        ALLOWED_EXTENSIONS={"pdf", "png", "jpg", "jpeg", "gif", "webp", "ppt", "pptx", "doc", "docx", "txt", "md", "zip"},
        WTF_CSRF_TIME_LIMIT=None,
        START_SCHEDULER=os.environ.get("HACKTRACK_SCHEDULER", "1") == "1",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    setup_logging(app)
    csrf.init_app(app)
    db.init_app(app)
    if not os.path.exists(app.config["DATABASE"]):
        db.init_db(app.config["DATABASE"])
    sprites.write_static_tiles(app.static_folder)

    from .blueprints import auth, main, quests, party, feed, journal, profile, api
    for bp in (auth.bp, main.bp, quests.bp, party.bp, feed.bp, journal.bp, profile.bp, api.bp):
        app.register_blueprint(bp)
    csrf.exempt(api.bp)

    register_template_helpers(app)
    register_hooks(app)
    register_errors(app)

    if app.config["START_SCHEDULER"] and not app.testing and (
            not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true"):
        from .services.notify import start_scheduler
        try:
            start_scheduler(app)
        except Exception:
            app.logger.exception("scheduler failed to start; reminders will run on page loads only")
    return app


def register_template_helpers(app):
    app.jinja_env.globals.update(
        sprite=sprites.sprite, icon=sprites.icon, type_icon=sprites.type_icon, C=constants,
        countdown=countdown, urgency_bucket=urgency_bucket,
    )
    app.jinja_env.filters["pretty"] = pretty_date
    app.jinja_env.filters["tojson_safe"] = lambda v: json.dumps(v)

    @app.template_filter("shortdt")
    def shortdt(value):
        dt = parse_dt(value)
        return dt.strftime("%d %b, %H:%M") if dt else ""

    @app.template_filter("inr")
    def inr(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return value
        if value >= 1e7:
            return f"Rs {value / 1e7:.1f} Cr"
        if value >= 1e5:
            return f"Rs {value / 1e5:.1f} L"
        return f"Rs {value:,.0f}"


def register_hooks(app):
    @app.before_request
    def load_user():
        g.user = None
        uid = session.get("user_id")
        if uid:
            g.user = User.get(db.get_db(), uid)
            if g.user is None:
                session.clear()

    @app.context_processor
    def inject_hud():
        if not g.get("user") or request.endpoint in (None, "static"):
            return {}
        from .services.game import hud
        try:
            data = hud(db.get_db(), g.user)
        except Exception:
            app.logger.exception("HUD failed")
            data = None
        popups = session.pop("popups", [])
        return {"hud": data, "popups": popups}

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp


def register_errors(app):
    def wants_json():
        return request.path.startswith("/api/") or request.is_json

    @app.errorhandler(404)
    def not_found(e):
        if wants_json():
            return jsonify(error="not found"), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(e):
        if wants_json():
            return jsonify(error="file too large (5 MB max)"), 413
        return render_template("errors/error.html", code=413, title="Inventory full",
                               message="That file is over 5 MB. Compress it or store a link instead."), 413

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        if wants_json():
            return jsonify(error="session expired, reload the page"), 400
        return render_template("errors/error.html", code=400, title="Save point expired",
                               message="Your form expired. Go back, reload the page and try again."), 400

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("500 on %s", request.path)
        if wants_json():
            return jsonify(error="server error"), 500
        return render_template("errors/500.html"), 500
