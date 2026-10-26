"""Reset the database and fill it with a demo world.

    python seed.py            -> fresh database with demo user  demo / demo1234
    python seed.py --keep     -> keep existing data, only add the demo world if it is missing

Also writes widget_config.json so the Tkinter desktop widget works straight away.
"""
import json
import os
import random
import sys
from datetime import timedelta

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import connect, init_db, skill_id
from app.services import notify, sample, xp as xp_service
from app.utils import now

DEMO_TOKEN = "demo-widget-token-change-me"
PLAYERS = [
    # username, display name, look, college, year, branch, bio, skills
    ("demo", "Riya Kapoor", "coder", "Chitkara University", 3, "CSE",
     "Backend-leaning builder. Flask, data and a weakness for 36-hour hackathons.",
     {"Python": 5, "Flask": 4, "SQL": 4, "Data Analysis": 4, "Machine Learning": 3, "UI/UX": 3,
      "Public Speaking": 4, "Pitching": 3, "React": 2, "DSA": 3, "Java": 2, "Research Writing": 3}),
    ("kabir", "Kabir Mehta", "knight", "Chitkara University", 3, "CSE", "Frontend wizard.",
     {"React": 5, "JavaScript": 5, "Node.js": 4, "UI/UX": 2, "HTML/CSS": 5}),
    ("meera", "Meera Nair", "ranger", "Chitkara University", 2, "Design", "UI/UX designer and pitch lead.",
     {"UI/UX": 5, "Figma": 5, "Pitching": 4, "Public Speaking": 4}),
    ("arjun", "Arjun Singh", "astro", "Chitkara University", 4, "AIML", "ML engineer, Kaggle grinder.",
     {"Machine Learning": 5, "Deep Learning": 4, "Python": 4, "Cloud": 3, "Data Analysis": 4}),
]
FEED = [
    ("kabir", "hackathon", "Hack2Skill GenAI Sprint", 9, "Rs 1,00,000", "Build with open LLMs in 48h. Teams of 2-4.", "genai,online"),
    ("meera", "competition", "Design Week Poster Challenge", 5, "Rs 15,000", "Campus design club poster competition.", "design,campus"),
    ("arjun", "research", "IIIT Hyderabad Summer Research (SPIRE)", 22, "Stipend", "8-week research internship in NLP and vision labs.", "research,nlp"),
    ("kabir", "workshop", "GitHub Campus Expert Git Workshop", 3, "", "Hands-on Git and open-source session in Lab 2.", "git,campus"),
    ("arjun", "internship", "Sarvam AI Research Intern", 15, "Rs 60,000/month", "Remote research internship on Indic LLMs.", "ai,remote"),
    ("meera", "scholarship", "Women in Tech Scholarship 2026", 19, "Rs 50,000", "For women in 2nd/3rd year of any engineering branch.", "women,merit"),
]


def seed(db_path, reset=True):
    init_db(db_path, reset=reset)
    conn = connect(db_path)
    today = now()
    rng = random.Random(7)
    ids = {}
    for username, name, look, college, year, branch, bio, skills in PLAYERS:
        row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if row:
            ids[username] = row["id"]
            continue
        cur = conn.execute(
            "INSERT INTO users (username, email, password_hash, display_name, avatar_look, college, year, branch, bio, "
            "interests, onboarded, api_token, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
            (username, f"{username}@hacktrack.local", generate_password_hash("demo1234"), name, look, college, year,
             branch, bio, "hackathons, AI, product", DEMO_TOKEN if username == "demo" else None,
             (today - timedelta(days=380)).strftime("%Y-%m-%d %H:%M")))
        ids[username] = cur.lastrowid
        for skill, prof in skills.items():
            conn.execute("INSERT INTO user_skills (user_id, skill_id, proficiency) VALUES (?, ?, ?)",
                         (cur.lastrowid, skill_id(skill, conn), prof))
    conn.commit()

    demo = ids["demo"]
    if not conn.execute("SELECT 1 FROM opportunities WHERE user_id = ?", (demo,)).fetchone():
        sample.load_sample(conn, demo, today)
        # teammates get a few quests too so their Hall of Fame pages look alive
        for username in ("kabir", "meera", "arjun"):
            sample.load_sample(conn, ids[username], today, history_xp=True, seed=rng.randint(1, 999))

        sih = conn.execute("SELECT id FROM opportunities WHERE user_id = ? AND title LIKE 'Smart India Hackathon 2026%'",
                           (demo,)).fetchone()["id"]
        team = conn.execute("INSERT INTO teams (name, owner_id, opportunity_id) VALUES ('Pixel Pirates', ?, ?)", (demo, sih)).lastrowid
        for username, role in (("demo", "leader"), ("kabir", "frontend"), ("meera", "design + pitch"), ("arjun", "ml")):
            conn.execute("INSERT INTO team_members (team_id, user_id, role, status) VALUES (?, ?, ?, 'active')",
                         (team, ids[username], role))
        rounds = [r["id"] for r in conn.execute("SELECT id FROM rounds WHERE opportunity_id = ? ORDER BY seq", (sih,))]
        tasks = [("Finalise problem statement", "demo", "done", 0), ("Draft PPT for screening", "meera", "doing", 0),
                 ("Landing page prototype", "kabir", "doing", 1), ("Train baseline model", "arjun", "todo", 1),
                 ("Backend API skeleton", "demo", "todo", 1), ("Rehearse finale pitch", "meera", "todo", 2)]
        for title, who, status, rix in tasks:
            conn.execute("INSERT INTO tasks (team_id, round_id, assignee_id, title, status, due_date, created_by) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (team, rounds[rix] if rix < len(rounds) else None, ids[who], title, status,
                          (today + timedelta(days=3 + rix * 10)).strftime("%Y-%m-%d %H:%M"), demo))
        for msg in ("Riya Kapoor formed the party", "Kabir Mehta joined the party", "Meera Nair joined the party",
                    "Arjun Singh joined the party", "Riya Kapoor added task 'Finalise problem statement'",
                    "Meera Nair moved 'Draft PPT for screening' to doing"):
            conn.execute("INSERT INTO team_log (team_id, user_id, message) VALUES (?, ?, ?)", (team, demo, msg))

        for username, qtype, title, offset, prize, desc, tags in FEED:
            post = conn.execute(
                "INSERT INTO feed_posts (user_id, college, type, title, description, link, deadline, prize_text, tags) "
                "VALUES (?, 'Chitkara University', ?, ?, ?, ?, ?, ?, ?)",
                (ids[username], qtype, title, desc, f"https://example.com/{title.lower().replace(' ', '-')}",
                 (today + timedelta(days=offset)).strftime("%Y-%m-%d 23:59"), prize, tags)).lastrowid
            for voter in rng.sample(list(ids.values()), rng.randint(1, 4)):
                conn.execute("INSERT OR IGNORE INTO feed_votes (post_id, user_id) VALUES (?, ?)", (post, voter))
        conn.commit()
        for uid in ids.values():
            xp_service.check_badges(conn, uid, today.date())
        notify.scan_reminders(conn, today)
        conn.execute("INSERT OR IGNORE INTO notifications (user_id, kind, message, link, dedupe_key) VALUES (?, 'party', ?, ?, ?)",
                     (demo, "Kabir Mehta moved 'Landing page prototype' to doing.", f"/party/{team}", "seed-party"))
        conn.commit()
    conn.close()
    return ids


def write_widget_config(path="widget_config.json"):
    config = {"server": "http://127.0.0.1:5000", "token": DEMO_TOKEN, "refresh_seconds": 60}
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2)
    except OSError as exc:
        print(f"Could not write {path}: {exc}")


if __name__ == "__main__":
    app = create_app({"START_SCHEDULER": False})
    keep = "--keep" in sys.argv
    seed(app.config["DATABASE"], reset=not keep)
    write_widget_config(os.path.join(os.path.dirname(os.path.abspath(__file__)), "widget_config.json"))
    print("Seeded HackTrack. Log in with  demo / demo1234  at http://127.0.0.1:5000")
