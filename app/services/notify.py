"""Reminders: in-app notifications at 7d/2d/1d before deadlines, plus optional Telegram and email.

Telegram needs TELEGRAM_BOT_TOKEN, email needs SMTP_HOST/SMTP_USER/SMTP_PASSWORD. Without them
everything still works through the in-app bell.
"""
import json
import logging
import os
import smtplib
import urllib.parse
import urllib.request
from email.message import EmailMessage

from ..utils import days_left, now as _now, parse_dt

log = logging.getLogger("hacktrack.notify")
WINDOWS = [(1, "1 day"), (2, "2 days"), (7, "7 days")]


def notify(db, user_id, message, link="", kind="info", dedupe_key=None):
    """INSERT OR IGNORE so the same reminder is only created once. Returns True when new. # CO3"""
    cur = db.execute(
        "INSERT OR IGNORE INTO notifications (user_id, kind, message, link, dedupe_key) VALUES (?, ?, ?, ?, ?)",
        (user_id, kind, message, link, dedupe_key))
    db.commit()
    return cur.rowcount > 0


def due_items(db, user_id=None):
    """Upcoming quest and round deadlines (subquery keeps only open quests)."""
    where = "AND o.user_id = ?" if user_id else ""
    args = (user_id,) if user_id else ()
    quests = db.execute(
        f"SELECT o.id, o.user_id, o.title, o.deadline, 'quest' AS kind, o.id AS opp_id FROM opportunities o "
        f"WHERE o.status IN ('interested','preparing','registered') {where}", args).fetchall()
    rounds = db.execute(
        f"SELECT r.id, o.user_id, o.title || ': ' || r.name AS title, r.deadline, 'round' AS kind, o.id AS opp_id "
        f"FROM rounds r JOIN opportunities o ON o.id = r.opportunity_id "
        f"WHERE r.status = 'pending' AND o.id IN (SELECT id FROM opportunities WHERE status NOT IN ('won','rejected')) {where}",
        args).fetchall()
    return [dict(r) for r in (*quests, *rounds)]


def scan_reminders(db, ref=None, user_id=None):
    """Create reminder notifications for deadlines inside the 7d/2d/1d windows. Returns count created."""
    ref = ref or _now()
    created = 0
    for item in due_items(db, user_id):
        d = days_left(item["deadline"], ref)
        if d is None or d < 0:
            continue
        for limit, label in WINDOWS:
            if d <= limit:
                key = f"rem-{item['kind']}-{item['id']}-{limit}"
                msg = f"⏰ {item['title']} is due in under {label} ({parse_dt(item['deadline']).strftime('%d %b %H:%M')})."
                if notify(db, item["user_id"], msg, f"/quests/{item['opp_id']}", "reminder", key):
                    created += 1
                    _external(db, item["user_id"], msg)
                break  # only the tightest window fires
    return created


def _external(db, user_id, message):
    user = db.execute("SELECT email, telegram_chat_id, email_reminders FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return
    if user["telegram_chat_id"]:
        send_telegram(user["telegram_chat_id"], message)
    if user["email_reminders"]:
        send_email(user["email"], "HackTrack reminder", message)


def send_telegram(chat_id, text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return False
    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=8) as resp:
            return json.loads(resp.read()).get("ok", False)
    except Exception:
        log.exception("telegram send failed")
        return False


def send_email(to, subject, body):
    host = os.environ.get("SMTP_HOST")
    if not host:
        return False
    try:
        msg = EmailMessage()
        msg["From"] = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "hacktrack@localhost"))
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", 587)), timeout=10) as smtp:
            smtp.starttls()
            if os.environ.get("SMTP_USER"):
                smtp.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
            smtp.send_message(msg)
        return True
    except Exception:
        log.exception("email send failed")
        return False


def start_scheduler(app):
    """APScheduler job that scans reminders every 30 minutes."""
    from apscheduler.schedulers.background import BackgroundScheduler
    from ..db import connect

    def job():
        conn = connect(app.config["DATABASE"])
        try:
            count = scan_reminders(conn)
            if count:
                log.info("scheduler created %s reminders", count)
        except Exception:
            log.exception("reminder job failed")
        finally:
            conn.close()

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(job, "interval", minutes=30, id="reminders", next_run_time=_now())
    scheduler.start()
    return scheduler
