# Screenshots for the report

Run `python seed.py` then `python run.py`, log in as **demo / demo1234**, and capture these in order.
Each entry has a short paragraph you can paste under "Implementation".

## Frontend (web app)

1. **Landing page** — `/`
   The "Press Start" screen styled like a retro game title card: a neon CRT frame, the HACKTRACK logo in
   Press Start 2P, a pixel avatar, cat and tree, and a scrolling marquee. START leads to sign-up; "Play the demo"
   pre-fills the demo login.

2. **Sign up / Log in** — `/signup`, `/login`
   Accounts use Werkzeug password hashing and Flask sessions; every form carries a Flask-WTF CSRF token.
   Validation errors appear inline under each field.

3. **Create your player (onboarding)** — `/onboarding`
   Players choose one of four original pixel avatars and record college, year, branch, interests and
   skill levels (1-5 stars). These drive eligibility checks and skill-matching.

4. **Deadline dashboard** — `/dashboard`
   Quests are grouped into colour-coded urgency buckets (overdue, under 48 h, this week, later). The
   "Do this first" panel ranks the top five by a transparent priority score; hovering a score shows the
   weighted breakdown. Search, filters and sort run server-side.

5. **Quest Map (World Map)** — `/map` (screenshot in both Day and Night themes)
   Every active quest is a pin on a winding pixel road, ordered by deadline. The road is drawn from SVG
   bezier curves and rendered at low resolution for a pixelated look; scenery is placed by a seeded generator.
   Pin colours: red pending, green done, gold won, grey locked, skull missed.

6. **Pin window** — click any signboard on the map
   A retro OS window with the quest's countdown, priority, skill fit, next back-plan steps (tickable) and
   quick actions: change status, add a note, open the roadmap or Inventory.

7. **Quest Roadmap** — `/quests/1/map`
   One quest's back-plan phases and rounds become pins leading to a trophy. Finishing a pin makes the avatar
   walk forward along the road; reaching the trophy triggers confetti, +150 XP and the Trophy Hunter badge.

8. **Quest detail** — `/quests/1`
   Status pipeline, priority score table, eligibility verdict, the back-plan checklist with a progress ring,
   the rounds timeline, skill-match (individual and party), Inventory, notes and Training Log links.

9. **New quest form** — `/quests/new`
   Type-specific fields appear for the chosen type (for example company and stipend for internships). Required
   skills use a "Python:3, React:2" format. A back-plan can be generated on save.

10. **Mission Briefing** — `/quests/briefing`
    Paste a WhatsApp forward or email into the CRT screen; the parser extracts title, type, deadlines, prize,
    team size, mode, eligibility and links. Every field shows a high/medium/low confidence tag and stays editable.

11. **Quest Board (Kanban)** — `/quests/board`
    Seven pipeline columns with HTML5 drag and drop. Each card also has a status dropdown so the board works
    with a keyboard. Moving forward awards XP once per step.

12. **All quests (list view)** — `/quests/`
    A readable data table with inline status changes, priority chips, CSV/JSON export and import.

13. **Insights** — `/insights`
    pandas aggregates quests by type, success rate, monthly activity and registration-to-submission time;
    numpy computes averages and percentiles. Chart.js renders the charts, with matplotlib PNGs as a fallback.
    Three plain-English insights are generated from the data. Includes the 12-month activity heatmap.

14. **Clash Detector** — `/clashes`
    Weeks with three or more deadlines (or six or more milestones) are flagged with advice on what to start
    early and what to skip. The HUD's HP bar drops as the week fills up.

15. **Eligibility** — `/eligibility`
    Each open quest is checked against the player's year, branch and college: Eligible, Not eligible or
    Check manually, with the reason.

16. **Party** — `/party/1`
    Team members, team skill-match (who covers which skill, and the gaps), a three-column task board per round
    and an activity log.

17. **Side Quests feed** — `/side-quests/`
    Players share opportunities with their college, upvote them and add them to their own quests in one click.

18. **Training Log** — `/training-log/`
    Post-mortems with what worked, what failed, lessons and a rating; full-text search and tag filters.

19. **Inventory** — Inventory section on `/quests/1`, and `/quests/inventory`
    Links and uploaded files (PDF, images, PPT) per quest, with image/PDF preview and download. Uploads use
    `secure_filename`, a 5 MB limit and an extension allowlist.

20. **Portfolio generator** — `/portfolio`
    LinkedIn-ready achievement bullets, a "Hackathons and Projects" resume section and an About blurb,
    with copy buttons and .txt / .md downloads.

21. **Badges & XP** — `/badges`
    Level, XP bar, XP sources (GROUP BY action) and the badge shelf with locked and unlocked badges.

22. **Hall of Fame (public profile)** — `/u/demo` (open in a private window to show it works logged out)
    The player card in a CRT frame, stats, badges, skills, heatmap and results timeline, with a copy-link
    button and a privacy toggle.

23. **Notifications** — bell in the HUD, and `/notifications`
    Reminders at 7, 2 and 1 days before deadlines (created by an APScheduler job), plus badge, level-up and
    party messages.

24. **Settings** — `/settings`
    Profile, skills, privacy, reminder channels, Simple mode, CRT scanlines, API token and data export.

25. **Simple mode** — toggle the eye icon in the HUD and re-shoot the dashboard
    Turns off pixel fonts, effects and animations for readability (also honours `prefers-reduced-motion`).

26. **Mobile view** — browser dev tools, 375 px wide, on `/dashboard` and `/map`
    Mobile-first layout with a console-style d-pad tab bar at the bottom.

27. **Game Over page** — `/anything-missing`
    Friendly 404 and 500 pages ("Press START").

28. **Desktop widget** — `python desktop_widget.py`
    An always-on-top Tkinter window with the next five deadlines, urgency colours and a live countdown.
    Stop the server and press REFRESH to show the graceful "Server offline" message.

## Backend artefacts

29. **Schema** — `schema.sql`
    Raw DDL: 19 tables with foreign keys, CHECK constraints (status values, ratings 1-5, file size ≤ 5 MB)
    and indexes on the hot query paths.

30. **Sample queries with output** — `docs/SAMPLE_QUERIES.md` (regenerate with `python docs/sample_queries.py`)
    JOINs, GROUP BY with aggregates, NOT IN subqueries, a recursive CTE and UPDATE/INSERT/DELETE, each with
    the real output from the seeded database.

31. **DB browser view** — open `instance/hacktrack.db` in DB Browser for SQLite
    Show the `opportunities`, `milestones` (parent_id tree) and `xp_events` tables.

32. **Test run** — `python -m pytest -v` (saved output: `docs/TEST_RUN.txt`)
    111 tests cover the parser (10 realistic texts), priority score, clash detector, skill-match, back-planner,
    eligibility, XP/levels/streaks, import/export, the map layout generator and every route.

33. **Log file** — `logs/hacktrack.log`
    The rotating log records database initialisation, CSV/JSON import results, rejected rows and any
    handled exceptions (CO2).

34. **REST API** — `http://127.0.0.1:5000/api/opportunities?upcoming=1&limit=5` with the bearer token
    JSON consumed by the desktop widget; without a token the API answers 401.

35. **Code highlights**
    `app/models.py` (class hierarchy), `app/services/planner.py` (recursive scheduler),
    `app/services/skillmatch.py` (map/reduce), `app/services/insights.py` (pandas/numpy).
