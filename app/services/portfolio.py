"""Hall of Fame builder: LinkedIn-ready bullets, a resume section and an About blurb from history."""
from functools import reduce

from ..utils import pretty_date

RESULT_VERBS = {
    "won": {"hackathon": "Won", "competition": "Won", "internship": "Selected for", "scholarship": "Awarded",
            "workshop": "Completed", "research": "Selected for"},
    "shortlisted": {"hackathon": "Finalist at", "competition": "Finalist in", "internship": "Shortlisted for",
                    "scholarship": "Shortlisted for", "workshop": "Completed", "research": "Shortlisted for"},
    "submitted": {"hackathon": "Built and submitted a project at", "competition": "Competed in",
                  "internship": "Applied to", "scholarship": "Applied for", "workshop": "Attended",
                  "research": "Applied to"},
}


def achievement_bullet(opp, skills=None, lesson=""):
    verb = RESULT_VERBS.get(opp.status, RESULT_VERBS["submitted"]).get(opp.type, "Took part in")
    parts = [f"{verb} {opp.title}"]
    if opp.organizer:
        parts.append(f"by {opp.organizer}")
    detail = []
    if opp.prize_text and opp.status == "won":
        detail.append(f"prize {opp.prize_text}")
    if opp.team_max > 1:
        detail.append(f"team of {opp.team_max}")
    if skills:
        detail.append("using " + ", ".join(list(skills)[:3]))
    bullet = " ".join(parts)
    if detail:
        bullet += f" ({'; '.join(detail)})"
    when = pretty_date(opp.result_at or opp.submitted_at or opp.deadline)
    bullet += f", {when[3:]}." if when else "."
    if lesson:
        bullet += f" Key takeaway: {lesson.strip().rstrip('.')}."
    return bullet


def generate(user, opps, skills_by_opp, lessons_by_opp, user_skills):
    """Build every portfolio artefact. Returns dict of strings/lists. # CO1 map/filter/reduce"""
    rank = {"won": 0, "shortlisted": 1, "submitted": 2}
    finished = sorted(filter(lambda o: o.status in rank, opps), key=lambda o: (rank[o.status], o.deadline))
    bullets = list(map(lambda o: achievement_bullet(o, skills_by_opp.get(o.id), lessons_by_opp.get(o.id, "")), finished))
    wins = len([o for o in finished if o.status == "won"])
    finals = len([o for o in finished if o.status == "shortlisted"])
    prize_total = reduce(lambda acc, o: acc + (o.prize_amount if o.status == "won" else 0), finished, 0)
    top_skills = ", ".join(list(user_skills)[:5]) or "building things"
    types = sorted({o.label.lower() + "s" for o in finished})

    about = (f"{user.name} is a {_year(user.year)} {user.branch or 'engineering'} student at "
             f"{user.college or 'college'} who has taken on {len(finished)} quests across "
             f"{', '.join(types) or 'hackathons and competitions'}"
             + (f", with {wins} win{'s' if wins != 1 else ''}" if wins else "")
             + (f" and {finals} final-round finish{'es' if finals != 1 else ''}" if finals else "")
             + f". Strongest in {top_skills}.")

    projects = [o for o in finished if o.type in ("hackathon", "competition", "research")]
    resume_lines = ["## Hackathons and Projects", ""]
    for o in projects:
        resume_lines.append(f"**{o.title}**, {o.organizer or o.label} | {pretty_date(o.deadline)}")
        resume_lines.append(f"- {achievement_bullet(o, skills_by_opp.get(o.id))}")
        if lessons_by_opp.get(o.id):
            resume_lines.append(f"- Learned: {lessons_by_opp[o.id]}")
        resume_lines.append("")
    if not projects:
        resume_lines.append("_Finish a hackathon or competition quest to fill this section._")
    resume_md = "\n".join(resume_lines).strip()

    linkedin = "\n".join(f"• {b}" for b in bullets) or "• Start your first quest to unlock achievements!"
    md = "\n".join([
        f"# {user.name}: Hall of Fame", "", "## About", about, "",
        "## Achievements", *[f"- {b}" for b in bullets], "", resume_md, "",
        f"_Generated with HackTrack. Total prize money won: Rs {prize_total:,.0f}_",
    ])
    txt = "\n".join([f"{user.name.upper()} - HALL OF FAME", "", "ABOUT", about, "",
                     "ACHIEVEMENTS", linkedin, "", resume_md.replace("## ", "").replace("**", "")])
    return {"bullets": bullets, "about": about, "resume_md": resume_md, "linkedin": linkedin,
            "md": md, "txt": txt, "wins": wins, "finals": finals, "prize_total": prize_total,
            "count": len(finished)}


def _year(year):
    return {1: "first-year", 2: "second-year", 3: "third-year", 4: "final-year"}.get(year or 0, "")
