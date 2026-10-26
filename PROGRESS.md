# HackTrack: build progress

Running checklist. Updated at the end of every phase so work can resume if interrupted.

## Phases
- [x] 1. Schema and models: `schema.sql` (19 tables, FKs, CHECKs, 10 indexes), `app/db.py`, `app/models.py`
- [x] 2. Auth and CRUD: signup/login/logout, onboarding, settings, quest CRUD, rounds, status pipeline
- [x] 3. Design system, pixel UI kit and sprites: `static/css/pixel.css` (day + night tokens, Simple mode),
      `app/sprites.py` (original pixel art → SVG), `static/js/app.js`
- [x] 4. Core pages: landing, dashboard, list, Kanban, quest detail, forms, notifications, 404/500
- [x] 5. Quest Map and XP/HUD: world map + per-quest roadmap, walking avatar, trophy victory, HUD with
      level, XP, streak and HP
- [x] 6. Signature features: Mission Briefing parser, rounds timeline, back-planner, skill-match, portfolio,
      insights (pandas/numpy/matplotlib + Chart.js), .ics export
- [x] 7. Extras: priority score, clash detector, eligibility, reminders (APScheduler, Telegram/SMTP hooks),
      heatmap + badges, Hall of Fame, Party, Side Quests, Training Log, Inventory, CSV/JSON import-export
- [x] 8. Desktop widget and API: `desktop_widget.py`, `/api/opportunities`, `/api/stats`
- [x] 9. Tests, seed data and docs: 111 pytest tests passing, `seed.py`, README, `docs/*`

## Verification done
- `python -m pytest`: 111 passed (output saved in `docs/TEST_RUN.txt`)
- Every route hit with the Flask test client (see `tests/test_routes.py`)
- Clicked through in a real browser: landing, login, dashboard, world map (day + night), pin window,
  status change with avatar walk, quest roadmap, quest detail, insights, Kanban; desktop and 375 px mobile
- Desktop widget: window builds, API fetch works, offline and bad-token messages verified
- `python seed.py` from scratch, then `python docs/sample_queries.py` (all queries run)

## Decisions and assumptions
- `./inspo/` did not exist in the folder. The three reference images pasted in chat were copied in as
  `inspo/01-roadmap.jpg`, `02-portfolio.jpg`, `03-mission-briefing.jpg`. `04-retrobit-font` was not
  supplied, so its "chunky pixel type in a CRT TV + Press Start Button" idea is taken from the brief text.
  The inspo folder is reference only and is never served by Flask.
- Course outcome wording was not supplied. Code tags use: CO1 OOP/functional/recursion, CO2 files/
  exceptions/logging, CO3 SQLite + Flask + REST + Tkinter, CO4 NumPy/pandas/Matplotlib (see `docs/CO_MAPPING.md`).
- Status "Won / Selected" is one pipeline value (`won`); the label shows "Selected" for internships,
  research and scholarships. "Rejected / Missed" is `rejected`; overdue open quests show as missed on the map.
- Prize values are stored in rupees for the priority score; dollar amounts are converted at a fixed Rs 83.
- Effort hours default per quest type (polymorphic `effort_estimate()`); the planner assumes 3 study hours/day.
- Training Log search uses SQL `LIKE` (portable everywhere) rather than SQLite FTS5.
- Forms use Flask-WTF for CSRF only; validation is hand-written so error messages stay game-friendly.
- Map progress (where the avatar last stood) is remembered per browser in localStorage so it can replay the
  walk when you return after finishing something elsewhere.
- The demo account (`demo` / `demo1234`) and its widget token are public by design for the college demo.

## Known limitations
- Telegram and SMTP senders are implemented but untested against live services (no credentials here);
  in-app reminders are fully tested.
- Chart.js loads from a CDN; offline, the Insights page falls back to matplotlib PNGs automatically.
- Pixel sprites are inline SVG, so pages are 60-350 KB uncompressed (gzip on a real server shrinks this a lot).
- The reminder scheduler runs in-process; run one worker (as in the Procfile). Duplicate reminders are
  prevented by a UNIQUE dedupe key anyway.
- The Tkinter widget uses Press Start 2P / VT323 only if those fonts are installed locally, else Courier/Consolas.
