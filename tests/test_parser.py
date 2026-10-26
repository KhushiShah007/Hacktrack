"""Mission Briefing parser: 10 realistic pasted texts."""
from datetime import timedelta

import pytest

from app.services.parser import confidence_score, parse_briefing

from .conftest import REF

SAMPLES = {
    "hackoverflow": (
        "📢 HackOverflow 3.0 is LIVE!\n36-hour national hackathon by IEEE Student Branch.\n"
        "Teams of 2-4 members. Prize pool ₹1,50,000 + internships.\n"
        "Registration deadline: 15th November, 11:59 PM\nPPT round results: 20 Nov\nOffline at Main Campus.\n"
        "Open to all B.Tech 2nd to 4th year students.\nRegister: https://hackoverflow.example.dev"),
    "internship": (
        "Hi all! Zeta Labs is hiring Summer Interns (Backend, Python/Flask, SQL).\n"
        "Stipend: Rs 30,000/month. Work from home.\nApply by 30 Dec 2026: https://forms.gle/zeta-intern\n"
        "Only 3rd year CSE/IT students eligible."),
    "scholarship": (
        "Reliance Foundation Scholarship 2026 for first-year UG students. Amount: ₹2 lakh. "
        "Last date to apply: 10/12/2026. Apply at www.scholarships.example.org"),
    "workshop": (
        "Join our hands-on Git & GitHub Workshop this Saturday, 7th Nov at 10 AM in Lab 2! "
        "Free certificate for all attendees. Register before 6 Nov: https://lu.ma/git-workshop"),
    "contest": (
        "CodeSprint 2026 - National Coding Contest by CodeChef\nIndividual participation. Prizes worth INR 50k.\n"
        "Contest date: 22 November 2026, 9 PM IST\nRegistrations close on 20th Nov.\nhttps://www.codechef.com/CODESPRINT"),
    "research": (
        "IISc Summer Research Fellowship 2027: applications open for 2nd and 3rd year students of CSE, ECE and EEE. "
        "Stipend ₹12,500 per month. Apply on or before 31 January 2027 at https://www.ias.ac.in/srfp"),
    "whatsapp": (
        "*HACK-A-THON ALERT* 🚀\n\n*Code for Bharat 2.0*\n📅 Last date: Nov 28\n👥 Team size: up to 4\n"
        "💰 Prize pool: $5,000\n🌐 Mode: Hybrid (Delhi + online)\nRegister 👉 bit.ly/cfb2"),
    "email": (
        "Subject: Microsoft Engage 2027 - Application Open\n\nDear Student,\n"
        "Microsoft Engage mentorship program is open for 2nd year students (CSE/IT/ECE).\nTimeline:\n"
        "- Application deadline: 5 Dec 2026\n- Online Assessment: 12 Dec 2026\n- Interviews: 20 Dec 2026\n"
        "Stipend: INR 80,000. Apply: https://careers.microsoft.com/engage"),
    "webinar": (
        "Webinar: Intro to Machine Learning with Python\nSpeaker: Dr. A. Rao (IIT Madras)\n"
        "Date: 3rd December 2026 | 6:00 PM | Zoom\nE-certificate for all. Register by 1 Dec."),
    "vague": "Check out this cool design challenge for UI/UX folks, prizes for top 3!",
}


def parsed(key):
    return parse_briefing(SAMPLES[key], ref=REF)


def v(result, field):
    return result[field]["value"]


def test_hackathon_poster():
    r = parsed("hackoverflow")
    assert "HackOverflow 3.0" in v(r, "title")
    assert v(r, "type") == "hackathon"
    assert v(r, "deadline") == "2026-11-15 23:59"
    assert r["deadline"]["confidence"] == "high"
    assert v(r, "prize_amount") == 150000
    assert (v(r, "team_min"), v(r, "team_max")) == (2, 4)
    assert v(r, "mode") == "offline"
    assert v(r, "link") == "https://hackoverflow.example.dev"
    assert v(r, "eligible_years") == "2,3,4"
    assert v(r, "organizer") == "IEEE Student Branch"
    assert any(rd["deadline"].startswith("2026-11-20") for rd in v(r, "rounds"))


def test_internship_whatsapp_greeting():
    r = parsed("internship")
    assert v(r, "title").startswith("Zeta Labs is hiring")
    assert v(r, "type") == "internship"
    assert v(r, "deadline") == "2026-12-30 23:59"
    assert v(r, "prize_amount") == 30000
    assert v(r, "mode") == "online"
    assert v(r, "eligible_years") == "3"
    assert set(v(r, "eligible_branches").split(",")) == {"CSE", "IT"}
    assert {"Python", "Flask", "SQL"} <= set(v(r, "skills"))


def test_scholarship_lakh_and_numeric_date():
    r = parsed("scholarship")
    assert v(r, "type") == "scholarship"
    assert v(r, "deadline") == "2026-12-10 23:59"  # dd/mm/yyyy
    assert v(r, "prize_amount") == 200000
    assert v(r, "link") == "https://www.scholarships.example.org"
    assert v(r, "eligible_years") == "1"


def test_workshop_with_time_and_register_by():
    r = parsed("workshop")
    assert v(r, "type") == "workshop"
    assert v(r, "deadline") == "2026-11-06 23:59"
    assert any(rd["deadline"] == "2026-11-07 10:00" for rd in v(r, "rounds"))
    assert v(r, "link") == "https://lu.ma/git-workshop"


def test_contest_solo_and_k_suffix():
    r = parsed("contest")
    assert v(r, "title") == "CodeSprint 2026"
    assert v(r, "type") == "competition"
    assert (v(r, "team_min"), v(r, "team_max")) == (1, 1)
    assert v(r, "prize_amount") == 50000
    assert v(r, "deadline") == "2026-11-20 23:59"
    assert v(r, "organizer") == "CodeChef"


def test_research_years_and_branches():
    r = parsed("research")
    assert v(r, "type") == "research"
    assert v(r, "deadline") == "2027-01-31 23:59"
    assert v(r, "eligible_years") == "2,3"
    assert set(v(r, "eligible_branches").split(",")) == {"CSE", "ECE", "EEE"}


def test_whatsapp_banner_dollars_hybrid_shortlink():
    r = parsed("whatsapp")
    assert v(r, "title") == "Code for Bharat 2.0"
    assert v(r, "type") == "hackathon"
    assert v(r, "deadline") == "2026-11-28 23:59"
    assert (v(r, "team_min"), v(r, "team_max")) == (1, 4)
    assert v(r, "prize_text") == "$5,000"
    assert v(r, "prize_amount") == 5000 * 83
    assert v(r, "mode") == "hybrid"
    assert v(r, "link") == "https://bit.ly/cfb2"


def test_email_with_timeline_rounds():
    r = parsed("email")
    assert v(r, "title") == "Microsoft Engage 2027"
    assert v(r, "type") == "internship"
    assert v(r, "deadline") == "2026-12-05 23:59"
    names = [rd["name"] for rd in v(r, "rounds")]
    assert "Online Assessment" in names and "Interviews" in names
    assert v(r, "eligible_years") == "2"


def test_webinar_online_and_skills():
    r = parsed("webinar")
    assert v(r, "type") == "workshop"
    assert "Machine Learning" in v(r, "title")
    assert v(r, "mode") == "online"
    assert v(r, "deadline") == "2026-12-01 23:59"
    assert {"Machine Learning", "Python"} <= set(v(r, "skills"))


def test_vague_text_falls_back_with_low_confidence():
    r = parsed("vague")
    assert r["deadline"]["confidence"] == "low"
    assert v(r, "deadline") == (REF.replace(hour=23, minute=59) + timedelta(days=14)).strftime("%Y-%m-%d %H:%M")
    assert v(r, "link") == ""
    assert confidence_score(r) < confidence_score(parsed("hackoverflow"))


@pytest.mark.parametrize("key", list(SAMPLES))
def test_every_field_has_confidence(key):
    r = parsed(key)
    for field in r.values():
        assert field["confidence"] in ("high", "medium", "low")
    assert 0 <= confidence_score(r) <= 100
