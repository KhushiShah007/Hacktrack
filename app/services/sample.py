"""Realistic sample quests, shared by seed.py and the "Load sample data" button."""
import random
from datetime import timedelta

from ..db import skill_id
from ..models import Opportunity
from ..utils import now as _now
from . import planner, xp as xp_service

# (type, title, organizer, deadline offset days, status, prize_text, prize_amount, team (min,max), mode,
#  location, skills {name: importance}, rounds [(name, offset, status)], extra, eligibility (years, branches, colleges, text), tags)
SAMPLE_QUESTS = [
    ("hackathon", "Smart India Hackathon 2026 (Internal Round)", "MoE Innovation Cell", 5, "registered",
     "Rs 1,00,000", 100000, (6, 6), "offline", "Campus Auditorium", {"Python": 3, "Machine Learning": 2, "Pitching": 2},
     [("PPT Screening", 5, "pending"), ("Prototype Review", 20, "pending"), ("Grand Finale", 35, "pending")],
     {"theme": "Smart Automation", "platform": "SIH Portal"}, ("", "", "", "Any UG student, teams of exactly 6 with 1 woman member."), "sih,government,flagship"),
    ("hackathon", "HackCBS 9.0", "Shaheed Sukhdev College", 12, "interested", "Rs 2,50,000 pool", 250000, (2, 4),
     "offline", "New Delhi", {"React": 3, "Node.js": 2, "UI/UX": 2}, [("Application", 12, "pending"), ("Hacking Day", 26, "pending")],
     {"theme": "Open innovation", "platform": "Devfolio"}, ("", "", "", "Open to all college students."), "mlh,delhi"),
    ("internship", "Google Summer of Code 2027", "Google", 40, "interested", "$1,500 stipend", 124500, (1, 1), "online",
     "Remote", {"Python": 3, "Research Writing": 2}, [("Proposal", 40, "pending"), ("Results", 70, "pending")],
     {"company": "Google + open-source org", "role": "Contributor", "stipend": "$1500", "duration": "12 weeks"},
     ("", "", "", "18+ and enrolled or recently graduated."), "open-source,remote"),
    ("internship", "Microsoft Engage Mentorship", "Microsoft", 9, "preparing", "Rs 80,000/month", 80000, (1, 1), "online",
     "Remote", {"DSA": 3, "Java": 2, "Python": 1}, [("Applied", 9, "pending"), ("Online Assessment", 16, "pending"), ("Interview", 24, "pending")],
     {"company": "Microsoft", "role": "SWE Mentee", "stipend": "Rs 80,000", "duration": "4 weeks"}, ("2,3", "CSE,IT,ECE", "", ""), "big-tech"),
    ("workshop", "Amazon ML Summer School", "Amazon", 3, "registered", "", 0, (1, 1), "online", "Online",
     {"Machine Learning": 3, "Python": 2}, [], {"speaker": "Amazon Scientists", "certificate": "yes"}, ("2,3,4", "", "", ""), "ml,certificate"),
    ("competition", "Flipkart GRiD 7.0 Software Development Track", "Flipkart", 2, "registered", "Rs 4,00,000 + PPI", 400000,
     (1, 3), "online", "Online", {"DSA": 3, "Java": 2, "SQL": 1}, [("Coding Quiz", 2, "pending"), ("Semi-final", 14, "pending"), ("Grand Finale", 30, "pending")],
     {"domain": "coding", "platform": "Unstop"}, ("2,3,4", "", "", ""), "unstop,ppi"),
    ("scholarship", "Reliance Foundation UG Scholarship", "Reliance Foundation", 6, "preparing", "Rs 2,00,000", 200000, (1, 1),
     "online", "", {"Research Writing": 2}, [("Application", 6, "pending"), ("Aptitude Test", 20, "pending")],
     {"provider": "Reliance Foundation", "amount": "Rs 2 lakh", "renewable": "no"}, ("1", "", "", "First-year UG students only."), "merit"),
    ("competition", "ICPC Asia Amritapuri Regional Qualifier", "ICPC Foundation", 16, "registered", "Trophy + regional slot", 0,
     (3, 3), "online", "Online", {"DSA": 3, "C++": 3}, [("Online Qualifier", 16, "pending"), ("Regional", 45, "pending")],
     {"domain": "competitive programming", "platform": "CodeDrills"}, ("", "", "", ""), "cp,icpc"),
    ("research", "IIT Bombay Research Internship", "IIT Bombay", 21, "interested", "Rs 15,000/month", 15000, (1, 1),
     "offline", "Mumbai", {"Machine Learning": 2, "Research Writing": 3, "Python": 2}, [("Proposal", 21, "pending"), ("Interview", 35, "pending")],
     {"lab": "KReSIT", "professor": "Dept. of CSE", "duration": "8 weeks"}, ("2,3", "CSE,IT,AIML", "", ""), "research,summer"),
    ("research", "IISc Summer Research Fellowship (SRFP)", "Indian Academy of Sciences", 30, "interested", "Rs 12,500/month", 12500,
     (1, 1), "offline", "Bengaluru", {"Research Writing": 3, "Data Analysis": 2}, [("Application", 30, "pending")],
     {"lab": "IISc", "duration": "8 weeks"}, ("2,3", "", "", "Students in 2nd or 3rd year of UG."), "fellowship"),
    ("hackathon", "ETHIndia 2026", "Devfolio", 4, "preparing", "$50,000 in bounties", 4150000, (1, 4), "offline",
     "Bengaluru", {"Blockchain": 3, "JavaScript": 2, "React": 2}, [("Application", 4, "pending"), ("Hackathon Weekend", 33, "pending")],
     {"theme": "Ethereum", "platform": "Devfolio"}, ("", "", "", ""), "web3,bengaluru"),
    ("competition", "Unstop UX Design Sprint", "Unstop", 7, "interested", "Rs 30,000", 30000, (1, 2), "online", "",
     {"UI/UX": 3, "Figma": 3}, [("Design Submission", 7, "pending")], {"domain": "design", "platform": "Unstop"}, ("", "", "", ""), "design"),
    ("competition", "Kaggle Playground: Student Edition", "Kaggle", 25, "interested", "Kaggle swag", 2000, (1, 3), "online", "",
     {"Machine Learning": 3, "Data Analysis": 3, "Python": 2}, [], {"domain": "data science", "platform": "Kaggle"}, ("", "", "", ""), "kaggle,ml"),
    ("scholarship", "Aditya Birla Scholarship", "Aditya Birla Group", 18, "interested", "Rs 1,80,000", 180000, (1, 1), "online", "",
     {"Research Writing": 2, "Public Speaking": 2}, [("Essay", 18, "pending"), ("Interview", 40, "pending")],
     {"provider": "Aditya Birla Group", "amount": "Rs 1.8 lakh/yr", "renewable": "yes"}, ("1", "", "IIT,BITS,NIT", "Only first-year students at listed IITs, BITS and NITs."), "merit"),
    ("workshop", "AWS Cloud Bootcamp (Campus)", "AWS Cloud Club", 1, "registered", "", 0, (1, 1), "offline", "Lab 4",
     {"Cloud": 3, "DevOps": 1}, [], {"speaker": "AWS Community Builders", "certificate": "yes"}, ("", "", "", ""), "cloud,campus"),
    ("workshop", "Postman API Student Expert", "Postman", 10, "interested", "", 0, (1, 1), "online", "",
     {"JavaScript": 1, "Node.js": 2}, [], {"speaker": "Postman", "certificate": "yes"}, ("", "", "", ""), "api,badge"),
    ("hackathon", "HackerEarth Climate Hack", "HackerEarth", 4, "interested", "Rs 75,000", 75000, (2, 4), "online", "",
     {"Python": 2, "Data Analysis": 2, "UI/UX": 1}, [("Idea Submission", 4, "pending")], {"theme": "Climate", "platform": "HackerEarth"}, ("", "", "", ""), "climate"),
    ("internship", "Goldman Sachs Engineering Virtual Internship", "Goldman Sachs", 13, "registered", "", 0, (1, 1), "online", "",
     {"Java": 2, "DSA": 2, "Finance": 1}, [("Applied", 13, "pending"), ("HireVue", 22, "pending")],
     {"company": "Goldman Sachs", "role": "Engineering Intern", "duration": "6 weeks"}, ("3", "", "", ""), "fintech"),
    ("internship", "Infosys InStep Global Internship", "Infosys", 28, "interested", "Rs 40,000/month", 40000, (1, 1), "offline",
     "Mysuru", {"Java": 2, "SQL": 2, "Cloud": 1}, [("Applied", 28, "pending")], {"company": "Infosys", "role": "Intern"}, ("3,4", "", "", ""), "it-services"),
    ("competition", "TCS CodeVita Season 13", "TCS", 6, "registered", "$10,000", 830000, (1, 1), "online", "",
     {"DSA": 3, "C++": 2}, [("Round 1", 6, "pending"), ("Round 2", 25, "pending")], {"domain": "coding", "platform": "TCS iON"}, ("", "", "", ""), "coding"),
    # ----- history (results) -----
    ("hackathon", "MLH Local Hack Day: Build", "Major League Hacking", -40, "won", "Rs 10,000", 10000, (1, 4), "online", "",
     {"Flask": 2, "Python": 3}, [("Submission", -40, "cleared"), ("Judging", -38, "cleared")], {"theme": "Open", "platform": "MLH"}, ("", "", "", ""), "mlh"),
    ("hackathon", "Smart India Hackathon 2025", "MoE Innovation Cell", -300, "shortlisted", "Rs 1,00,000", 100000, (6, 6), "offline",
     "Pune", {"Python": 3, "Machine Learning": 2}, [("PPT Screening", -330, "cleared"), ("Grand Finale", -300, "failed")],
     {"theme": "Agritech", "platform": "SIH Portal"}, ("", "", "", ""), "sih"),
    ("competition", "Code Gladiators 2026", "TechGig", -120, "rejected", "Rs 5,00,000", 500000, (1, 1), "online", "",
     {"DSA": 3}, [("Qualifier", -120, "failed")], {"domain": "coding", "platform": "TechGig"}, ("", "", "", ""), "coding"),
    ("hackathon", "GDSC Solution Challenge", "Google Developer Student Clubs", -200, "submitted", "$3,000", 249000, (2, 4), "online", "",
     {"Flutter": 2, "Cloud": 2, "UI/UX": 1}, [("Submission", -200, "cleared")], {"theme": "UN SDGs", "platform": "Google"}, ("", "", "", ""), "google,sdg"),
    ("hackathon", "Chitkara Inter-college Hackfest", "Chitkara University", -75, "won", "Rs 25,000", 25000, (2, 4), "offline",
     "Rajpura", {"Python": 2, "React": 2, "Pitching": 2}, [("PPT", -85, "cleared"), ("Finals", -75, "cleared")], {"theme": "EdTech"}, ("", "", "", ""), "campus"),
    ("competition", "Unstop FinTech Case Study", "Unstop", -150, "shortlisted", "Rs 50,000", 50000, (2, 3), "online", "",
     {"Finance": 2, "Pitching": 3, "Data Analysis": 2}, [("Case Submission", -165, "cleared"), ("Final Pitch", -150, "failed")],
     {"domain": "case study", "platform": "Unstop"}, ("", "", "", ""), "case-study"),
    ("internship", "Zeta Labs Summer Internship", "Zeta Labs", -90, "won", "Rs 25,000/month", 25000, (1, 1), "hybrid", "Chandigarh",
     {"Python": 3, "Flask": 2, "SQL": 2}, [("Applied", -110, "cleared"), ("OA", -102, "cleared"), ("Interview", -95, "cleared"), ("Offer", -90, "cleared")],
     {"company": "Zeta Labs", "role": "Backend Intern", "stipend": "Rs 25,000", "duration": "8 weeks"}, ("", "", "", ""), "startup"),
    ("workshop", "NPTEL Python for Data Science", "NPTEL / IIT Madras", -60, "won", "", 0, (1, 1), "online", "",
     {"Python": 2, "Data Analysis": 2}, [], {"speaker": "IIT Madras", "certificate": "yes"}, ("", "", "", ""), "certificate"),
    ("scholarship", "INSPIRE Scholarship", "DST India", -220, "rejected", "Rs 80,000/yr", 80000, (1, 1), "online", "",
     {}, [("Application", -220, "failed")], {"provider": "DST", "amount": "Rs 80,000"}, ("1", "", "", ""), "government"),
    ("competition", "Microsoft Learn AI Skills Challenge", "Microsoft", -20, "submitted", "Certification voucher", 3000, (1, 1), "online", "",
     {"Machine Learning": 2, "Cloud": 2}, [], {"domain": "AI", "platform": "Microsoft Learn"}, ("", "", "", ""), "ai,certificate"),
    ("hackathon", "Hack the Mountains 4.0", "HTM Community", -10, "shortlisted", "Rs 1,50,000", 150000, (2, 4), "offline", "Solan",
     {"React": 2, "Node.js": 2, "UI/UX": 2}, [("Online Round", -25, "cleared"), ("Finals", -10, "failed")], {"theme": "Tourism"}, ("", "", "", ""), "himachal"),
]

JOURNAL = {
    "MLH Local Hack Day: Build": ("Shipped a tiny Flask app in 6 hours", "Scoping to one feature; demo first, polish later.",
                                 "Wasted an hour on auth we did not need.", "Cut scope early and record the demo before polishing.", 5, "flask,scope"),
    "Smart India Hackathon 2025": ("SIH finale: so close", "Problem research with farmers gave us real data.",
                                   "Pitch ran over time and we missed Q&A.", "Rehearse the pitch with a timer, twice.", 4, "pitch,teamwork"),
    "Code Gladiators 2026": ("Qualifier did not go well", "Comfortable with arrays and strings.",
                             "Got stuck on DP and graphs under time pressure.", "Do 2 timed DP problems a day for a month.", 2, "dsa,dp"),
    "Chitkara Inter-college Hackfest": ("Won the campus hackfest!", "Clear roles: I did backend, Kabir frontend, Meera pitch.",
                                        "Merged late and broke the build once.", "Merge every 2 hours and keep main deployable.", 5, "teamwork,git"),
    "Unstop FinTech Case Study": ("Case study final", "Strong numbers and a clean deck.",
                                  "Judges wanted a go-to-market plan we did not have.", "Always include GTM and risks slides.", 3, "case-study,pitch"),
    "Hack the Mountains 4.0": ("Finalist at HTM", "Offline prototype that worked without internet.",
                               "UI was rough; judges noticed.", "Book 3 hours just for UI polish.", 4, "ui,pitch"),
    "Zeta Labs Summer Internship": ("Internship offer!", "Project walkthrough of my Flask app impressed them.",
                                    "Struggled on one SQL join question.", "Revise SQL joins and window functions before interviews.", 5, "interview,sql"),
}

ASSETS = {
    "MLH Local Hack Day: Build": [("github", "Source code", "https://github.com/example/quick-notes"),
                                  ("demo", "Live demo", "https://quick-notes.example.com")],
    "Chitkara Inter-college Hackfest": [("github", "Repo", "https://github.com/example/study-buddy"),
                                        ("ppt", "Pitch deck", "https://docs.google.com/presentation/d/example")],
    "Hack the Mountains 4.0": [("github", "Repo", "https://github.com/example/trail-guide")],
    "Smart India Hackathon 2026 (Internal Round)": [("ppt", "Draft PPT", "https://docs.google.com/presentation/d/sih-draft")],
}


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M")


def load_sample(db, user_id, today=None, history_xp=True, seed=42):
    """Insert the sample quest set for a user. Returns number of quests created. # CO3"""
    today = today or _now()
    rng = random.Random(seed + user_id)
    created = {}
    for (qtype, title, org, offset, status, prize_text, prize, team, mode, loc, skills, rounds, extra, elig, tags) in SAMPLE_QUESTS:
        deadline = (today + timedelta(days=offset)).replace(hour=23, minute=59)
        created_at = min(deadline - timedelta(days=rng.randint(12, 40)), today - timedelta(days=rng.randint(0, 3)))
        opp = Opportunity.create(
            qtype, user_id=user_id, title=title, organizer=org, prize_text=prize_text, prize_amount=prize,
            team_min=team[0], team_max=team[1], mode=mode, location=loc, status=status, deadline=_fmt(deadline),
            extra=extra, eligible_years=elig[0], eligible_branches=elig[1], eligible_colleges=elig[2],
            eligibility_text=elig[3], tags=tags, link=f"https://example.com/{title.lower().replace(' ', '-')[:40]}",
            description=f"{title} by {org}. Sample quest loaded by HackTrack.", source="sample")
        opp.save(db)
        reg = created_at + timedelta(days=rng.randint(1, 5)) if status not in ("interested", "preparing") else None
        sub = deadline - timedelta(hours=rng.randint(2, 30)) if status in ("submitted", "shortlisted", "won", "rejected") else None
        res = deadline + timedelta(days=rng.randint(2, 6)) if status in ("shortlisted", "won", "rejected") else None
        db.execute("UPDATE opportunities SET created_at=?, registered_at=?, submitted_at=?, result_at=? WHERE id=?",
                   (_fmt(created_at), reg and _fmt(reg), sub and _fmt(sub), res and _fmt(min(res, today)), opp.id))
        for name, importance in skills.items():
            db.execute("INSERT OR IGNORE INTO opportunity_skills (opportunity_id, skill_id, importance) VALUES (?, ?, ?)",
                       (opp.id, skill_id(name, db), importance))
        for seq, (rname, roff, rstatus) in enumerate(rounds, start=1):
            db.execute("INSERT INTO rounds (opportunity_id, seq, name, deadline, status) VALUES (?, ?, ?, ?, ?)",
                       (opp.id, seq, rname, _fmt((today + timedelta(days=roff)).replace(hour=23, minute=59)), rstatus))
        created[title] = (opp, created_at, reg, sub, res)
        if history_xp:
            xp_service.award(db, user_id, "add_quest", opp.id, when=_fmt(created_at))
            if reg:
                xp_service.award(db, user_id, "register", opp.id, when=_fmt(min(reg, today)))
            if sub and sub <= today:
                xp_service.award(db, user_id, "submit", opp.id, when=_fmt(sub))
            if res and status in ("shortlisted", "won"):
                xp_service.award(db, user_id, "shortlist" if status == "shortlisted" else "win", opp.id, when=_fmt(min(res, today)))
    db.commit()

    # back-plans for a few active quests, with early milestones ticked
    for title in ("Smart India Hackathon 2026 (Internal Round)", "ETHIndia 2026", "Microsoft Engage Mentorship",
                  "Reliance Foundation UG Scholarship", "MLH Local Hack Day: Build"):
        if title not in created:
            continue
        opp = created[title][0]
        plan_from = created[title][1] if opp.status == "won" else today
        milestones, _ = planner.build_plan(opp.type, opp.deadline, opp.effort_estimate(), plan_from)
        ids = planner.save_plan(db, opp.id, milestones)
        for mid, m in zip(ids, milestones):
            due = m["due_date"]
            if opp.status == "won" or due <= _fmt(today):
                db.execute("UPDATE milestones SET done = 1, done_at = ? WHERE id = ?", (due, mid))
                if history_xp:
                    xp_service.award(db, user_id, "finish_milestone", mid, when=due)
    db.commit()

    for title, (jt, worked, failed, lessons, rating, tags) in JOURNAL.items():
        if title in created:
            opp, *_rest, res = created[title]
            when = _fmt(min((res or today) + timedelta(days=1), today))
            db.execute("INSERT INTO journal_entries (user_id, opportunity_id, title, what_worked, what_failed, lessons, rating, tags, created_at) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (user_id, opp.id, jt, worked, failed, lessons, rating, tags, when))
            if history_xp:
                xp_service.award(db, user_id, "journal", opp.id, when=when)
    for title, items in ASSETS.items():
        if title in created:
            for cat, label, url in items:
                db.execute("INSERT INTO assets (opportunity_id, user_id, kind, category, label, url) VALUES (?, ?, 'link', ?, ?, ?)",
                           (created[title][0].id, user_id, cat, label, url))
    db.execute("UPDATE opportunities SET trophy_claimed = 1 WHERE user_id = ? AND title = ?", (user_id, "MLH Local Hack Day: Build"))
    db.commit()

    if history_xp:
        # sprinkle everyday activity across the year so the heatmap and streak look lived-in
        for back in range(365, 0, -1):
            day = today - timedelta(days=back)
            if back <= 5 or rng.random() < 0.28:
                for _ in range(rng.randint(1, 3)):
                    when = day.replace(hour=rng.randint(9, 22), minute=rng.randint(0, 59))
                    db.execute("INSERT INTO xp_events (user_id, action, points, ref, created_at) VALUES (?, 'finish_milestone', 5, 'daily', ?)",
                               (user_id, _fmt(when)))
        db.commit()
    xp_service.check_badges(db, user_id, today.date())
    return len(created)
