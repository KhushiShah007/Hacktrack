# Report notes (ready to paste)

## AIM

To design and implement HackTrack, a Python web application that helps college students track hackathons,
competitions, internships, scholarships, workshops and research programs in one place, plan their work
backwards from deadlines, match opportunities to team skills and turn their history into a shareable
profile, presented as a retro pixel-art game, while demonstrating object-oriented programming, functional
programming, file and exception handling, SQLite databases, a Flask web app, a Tkinter desktop widget and
data analysis with NumPy, pandas and Matplotlib.

## PROBLEM STATEMENT

College students learn about opportunities from scattered WhatsApp forwards, posters, emails and portals.
Deadlines are easy to miss, several events often clash in the same week, multi-round selections are hard
to follow, and students rarely know which opportunities fit their skills, whether they are eligible, or how
to start early enough. After an event, results and lessons are lost, and building a resume or LinkedIn
section from past achievements takes effort. Existing tools such as spreadsheets and generic to-do apps
do not understand rounds, team skills, eligibility rules or back-planning, and they are not motivating to use.
HackTrack solves this by turning each opportunity into a "quest": it parses pasted text into structured data,
prioritises what to do first, generates a dated milestone plan, detects deadline clashes, checks eligibility,
matches team skills, sends reminders and rewards progress with XP, badges and a visual quest map.

## SOFTWARE USED

| Category | Software |
|---|---|
| Language | Python 3.11+ (tested on Python 3.14) |
| Web framework | Flask 3, Jinja2 templates, Flask-WTF (CSRF protection), Werkzeug (password hashing, secure uploads) |
| Database | SQLite 3 through Python's built-in `sqlite3` module (raw SQL, no ORM) |
| Data analysis | pandas, NumPy, Matplotlib |
| Scheduling | APScheduler (background reminder jobs) |
| Date parsing | python-dateutil |
| Desktop GUI | Tkinter (Python standard library) |
| Frontend | HTML5, hand-written CSS, vanilla JavaScript, Chart.js (CDN), Google Fonts (Press Start 2P, VT323) |
| Testing | pytest |
| Tools | VS Code, Git, DB Browser for SQLite, a modern web browser |
| Deployment (optional) | Gunicorn on Render, or PythonAnywhere |
| OS | Windows 11 (also runs on Linux and macOS) |

## CONCLUSION

HackTrack brings every opportunity a student tracks into one gamified dashboard and quest map, so nothing
important slips past its deadline. The project applies the full course syllabus in one working product: an
OOP class hierarchy with polymorphism, lambda/map/filter/reduce and recursion, robust file handling with
exceptions and logging, a normalised SQLite database driven by raw SQL, a Flask web app with a REST API and a
Tkinter widget, and NumPy/pandas/Matplotlib analytics. With 111 passing automated tests and realistic seed
data, it is ready to be used and extended, for example with a mobile app or calendar sync.
