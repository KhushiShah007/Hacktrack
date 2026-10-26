"""SQLite access layer: raw sqlite3, no ORM, so all DDL/DML stays visible (CO3)."""
import logging
import os
import sqlite3

import click
from flask import current_app, g

from .constants import BADGES, SKILL_CATALOG

log = logging.getLogger("hacktrack.db")
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schema.sql")


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False, db=None):
    """SELECT helper with parameterized args. # CO3"""
    cur = (db or get_db()).execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=(), db=None, commit=True):
    """INSERT/UPDATE/DELETE helper returning lastrowid. # CO3"""
    conn = db or get_db()
    cur = conn.execute(sql, args)
    if commit:
        conn.commit()
    return cur.lastrowid


def init_db(path, reset=False):
    """Create tables from schema.sql and insert the badge and skill catalogs. # CO2 # CO3"""
    if reset and os.path.exists(path):
        os.remove(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = connect(path)
    try:
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            conn.executescript(fh.read())
        conn.executemany(
            "INSERT OR IGNORE INTO badges (code, name, description, icon) VALUES (?, ?, ?, ?)", BADGES
        )
        conn.executemany("INSERT OR IGNORE INTO skills (name, category) VALUES (?, ?)", SKILL_CATALOG)
        conn.commit()
        log.info("database initialised at %s", path)
    except (OSError, sqlite3.Error):
        log.exception("could not initialise database")
        raise
    finally:
        conn.close()


def skill_id(name, db=None):
    """Find or create a skill row by name."""
    row = query("SELECT id FROM skills WHERE name = ?", (name.strip(),), one=True, db=db)
    if row:
        return row["id"]
    return execute("INSERT INTO skills (name) VALUES (?)", (name.strip(),), db=db)


def init_app(app):
    app.teardown_appcontext(close_db)

    @app.cli.command("init-db")
    @click.option("--reset", is_flag=True, help="Delete the existing database first.")
    def init_db_command(reset):
        init_db(app.config["DATABASE"], reset=reset)
        click.echo("Initialised the database.")
