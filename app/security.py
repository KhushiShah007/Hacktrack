"""Session + token auth helpers."""
import secrets
from functools import wraps

from flask import g, redirect, request, url_for, jsonify, flash

from .db import get_db


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            if request.accept_mimetypes.best == "application/json" or request.is_json:
                return jsonify(error="login required"), 401
            flash("Press START and log in to continue.", "info")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def token_required(view):
    """Simple bearer-token auth for the read-only REST API (used by the Tkinter widget)."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") else request.args.get("token", "")
        if not token:
            return jsonify(error="missing token"), 401
        row = get_db().execute("SELECT id FROM users WHERE api_token = ?", (token,)).fetchone()
        if not row:
            return jsonify(error="invalid token"), 401
        g.api_user_id = row["id"]
        return view(*args, **kwargs)
    return wrapped


def new_token():
    return secrets.token_urlsafe(24)


def safe_next(target):
    """Only allow local redirects after login."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None
