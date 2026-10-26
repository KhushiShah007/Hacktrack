# Course Outcome mapping

The course's official CO wording was not supplied, so HackTrack uses these four outcomes
(adjust the labels to match your syllabus; the evidence stays the same):

| CO | Outcome (as used in code comments) |
|---|---|
| **CO1** | Apply Python fundamentals and OOP: classes, inheritance, polymorphism, dataclasses, lambda / `map` / `filter` / `functools.reduce`, recursion |
| **CO2** | Use modules, file handling, exception handling and logging to build robust programs |
| **CO3** | Build database-backed applications: SQLite DDL/DML with raw SQL, a Flask web app, a REST API and a Tkinter GUI |
| **CO4** | Analyse and visualise data with NumPy, pandas and Matplotlib |

Every key function carries a `# CO1` / `# CO2` / `# CO3` / `# CO4` tag. Search the code with
`grep -rn "# CO" app desktop_widget.py` to list them.

## Feature / module / file → CO

| Feature or module | File(s) | CO1 | CO2 | CO3 | CO4 | Evidence |
|---|---|:-:|:-:|:-:|:-:|---|
| Quest class hierarchy | `app/models.py` | ✔ | | ✔ | | `Opportunity` base + 6 subclasses override `stages()`, `effort_estimate()`, `describe()`; registry via `__init_subclass__`; `save()` runs INSERT/UPDATE |
| Round, Milestone, User, Team, Member, Badge | `app/models.py` | ✔ | | ✔ | | dataclasses; `Milestone.leaf_counts()` is recursive and uses `reduce` |
| Database schema | `schema.sql` | | | ✔ | | 19 tables, foreign keys with `ON DELETE CASCADE/SET NULL`, CHECK constraints, 10 indexes |
| DB access layer | `app/db.py` | | ✔ | ✔ | | parameterised `query()` / `execute()`, `init_db()` with try/except + logging |
| Seed data | `seed.py`, `app/services/sample.py` | | ✔ | ✔ | | 4 players, 31 quests per player, rounds, plans, teams, journal, feed, a year of XP |
| Auth + onboarding | `app/blueprints/auth.py` | | | ✔ | | Werkzeug password hashing, sessions, CSRF, validation |
| Quest CRUD, Kanban, list | `app/blueprints/quests.py`, `common.py`, `static/js/board.js` | ✔ | | ✔ | | `apply_filters()` uses `filter` + lambdas + `sorted(key=lambda)` |
| Mission Briefing parser | `app/services/parser.py` | ✔ | ✔ | | | regex, `dateutil` fuzzy parsing, keyword scoring, confidence levels |
| Round tracking + timeline | `quests.py`, `templates/quests/detail.html` | | | ✔ | | rounds table, UPDATE per round |
| Auto Back-Planner | `app/services/planner.py` | ✔ | | ✔ | | `_schedule()` recursively walks the template tree backwards from the deadline |
| Milestone ticking | `quests.toggle_milestone` | | | ✔ | | recursive CTE (`WITH RECURSIVE`) ticks a phase and all children |
| Team Skill-Match | `app/services/skillmatch.py` | ✔ | | | | weighted Jaccard with `map`/lambda, team vector with `reduce` |
| Portfolio generator | `app/services/portfolio.py`, `profile.py` | ✔ | ✔ | | | `filter` / `map` / `reduce`; .txt and .md downloads |
| Insights dashboard | `app/services/insights.py`, `templates/insights.html` | | | | ✔ | `pd.read_sql_query`, `groupby`, `np.mean/median/percentile`, matplotlib PNG fallback |
| Activity heatmap | `insights.heatmap()` | | | ✔ | ✔ | SQL `GROUP BY date()`, numpy percentiles for colour levels |
| Calendar export | `app/services/ics.py` | | ✔ | | | hand-written RFC 5545 text with line folding |
| Priority Score | `app/services/scoring.py` | ✔ | | | | weighted formula, `filter`/`map`/`sorted` for top-5 |
| Clash Detector | `app/services/clash.py` | ✔ | | | | `filter` + lambda, `defaultdict` week buckets |
| Eligibility Checker | `app/services/eligibility.py` | ✔ | | | | rule comparison with reasons |
| Reminders | `app/services/notify.py` | | ✔ | ✔ | | APScheduler job, `INSERT OR IGNORE` dedupe, optional Telegram/SMTP with try/except |
| XP, levels, streaks, badges | `app/services/xp.py` | ✔ | ✔ | ✔ | | recursive `streak_from()`, SQL badge rules, logged failures |
| Public profile, badges | `app/blueprints/profile.py` | | | ✔ | | privacy toggle |
| Party (team board) | `app/blueprints/party.py` | | | ✔ | | teams, team_members, tasks, team_log; subqueries for counts |
| Side Quests feed | `app/blueprints/feed.py` | | | ✔ | | `EXISTS` subqueries, votes with composite PK |
| Training Log | `app/blueprints/journal.py` | | | ✔ | | LIKE full-text search + tag filter |
| Inventory (uploads) | `quests.add_asset` | | ✔ | ✔ | | `secure_filename`, 5 MB limit, extension allowlist, OSError handling |
| CSV / JSON import-export | `app/services/io_utils.py` | | ✔ | ✔ | | `csv`, `json`, validation report, `UnicodeDecodeError` / `JSONDecodeError` / `csv.Error` handling |
| Rotating log file | `app/__init__.py` (`setup_logging`) | | ✔ | | | `RotatingFileHandler` → `logs/hacktrack.log` |
| REST API | `app/blueprints/api.py`, `app/security.py` | | | ✔ | | bearer-token auth, JSON |
| Desktop widget | `desktop_widget.py` | ✔ | ✔ | ✔ | | Tkinter classes, config file I/O, offline handling |
| Quest Map generator | `app/services/questmap.py`, `static/js/map.js` | ✔ | | | | bezier road, seeded `random.Random` scenery, collision checks |
| Pixel sprites | `app/sprites.py` | ✔ | ✔ | | | grid → SVG run-length merge, `lru_cache`, tiles written to disk |
| Tests | `tests/` | ✔ | ✔ | ✔ | ✔ | 111 pytest tests |
