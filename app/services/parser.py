"""Mission Briefing: turn a pasted poster caption / WhatsApp forward / email into quest fields.

Uses regex, dateutil fuzzy parsing and keyword heuristics. Every field comes back as
{"value": ..., "confidence": "high" | "medium" | "low"} so the UI can show how sure we are.
"""
import re
from datetime import timedelta

from dateutil import parser as dparser

from ..utils import now as _now

URL_RE = re.compile(r"(https?://[^\s<>\"')\]]+|(?:www\.|bit\.ly/|forms\.gle/|lu\.ma/|unstop\.com/|devfolio\.co/)[^\s<>\"')\]]+)", re.I)
MONEY_RE = re.compile(
    r"(?:(?:₹|rs\.?|inr|\$|usd)\s?(\d[\d,]*(?:\.\d+)?)\s*(k|l|lakh|lakhs|lac|cr|crore)?)"
    r"|(?:(\d[\d,]*(?:\.\d+)?)\s*(k|l|lakh|lakhs|lac|cr|crore)?\s*(?:₹|rs\.?|inr|rupees|/-))",
    re.I,
)
TEAM_RE = [
    (re.compile(r"team(?:s)?\s*(?:size)?\s*(?:of|:)?\s*(?:up\s*to|max(?:imum)?)\s*(\d+)", re.I), "max"),
    (re.compile(r"(\d+)\s*(?:-|to|–)\s*(\d+)\s*(?:members|people|participants|per team)", re.I), "range"),
    (re.compile(r"team(?:s)?\s*(?:size)?\s*(?:of|:)?\s*(\d+)\s*(?:-|to|–)\s*(\d+)", re.I), "range"),
    (re.compile(r"team(?:s)?\s*(?:size)?\s*(?:of|:)\s*(\d+)", re.I), "exact"),
    (re.compile(r"\b(solo|individual(?:ly)?|single participant)\b", re.I), "solo"),
]
DATE_KEYWORDS = re.compile(
    r"(deadline|last date|apply by|register by|registrations? (?:close|end)s?|submission|closes?|ends?|due|"
    r"before|till|until|round|date|on)\b", re.I)
DEADLINE_WORDS = re.compile(r"(deadline|last date|apply by|register by|registrations? (?:close|end)|closes?|due|till|until|before)", re.I)
MONTHS = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
DATE_LIKE = re.compile(
    rf"(\d{{1,2}}(?:st|nd|rd|th)?\s*(?:of\s*)?{MONTHS}\.?,?(?:\s*\d{{4}})?(?:[,\s]+(?:at\s*)?\d{{1,2}}(?::\d{{2}})?\s*(?:am|pm))?"
    rf"|{MONTHS}\.?\s*\d{{1,2}}(?:st|nd|rd|th)?,?\s*(?:\d{{4}})?"
    rf"|\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}"
    rf"|\d{{4}}-\d{{2}}-\d{{2}})",
    re.I,
)

TYPE_KEYWORDS = {
    "hackathon": ["hackathon", "hack-a-thon", "hack ", "buildathon", "ideathon", "codefest", "devfolio", "24 hour", "36 hour", "48 hour", "sih"],
    "internship": ["internship", "intern ", "stipend", "ppo", "hiring", "summer intern", "sde intern", "work from home"],
    "scholarship": ["scholarship", "fellowship grant", "financial aid", "tuition", "merit-cum-means", "bursary"],
    "workshop": ["workshop", "bootcamp", "webinar", "masterclass", "hands-on session", "seminar"],
    "research": ["research", "fellowship", "surf", "lab ", "professor", "paper", "summer research", "iisc", "iit "],
    "competition": ["competition", "contest", "challenge", "case study", "quiz", "olympiad", "coding round", "championship"],
}
MODE_KEYWORDS = {
    "hybrid": ["hybrid"],
    "online": ["online", "virtual", "remote", "work from home", "wfh", "zoom", "google meet"],
    "offline": ["offline", "in-person", "in person", "on campus", "on-site", "onsite", "venue"],
}
ELIGIBILITY_RE = re.compile(
    r"^.*(eligib|open to|who can apply|for students|undergrad|b\.?tech|b\.?e\b|\byear\b|\bbranch|ug\s*/\s*pg|freshers).*$",
    re.I | re.M)
YEAR_RE = re.compile(r"\b([1-4])(?:st|nd|rd|th)?\s*(?:,|&|and|/|-|to)?\s*(?:([1-4])(?:st|nd|rd|th)?\s*)?(?:,|&|and|/|-|to)?\s*(?:([1-4])(?:st|nd|rd|th)?\s*)?year", re.I)
BRANCH_WORDS = {"cse": "CSE", "computer science": "CSE", "it": "IT", "information technology": "IT",
                "ece": "ECE", "electronics": "ECE", "eee": "EEE", "electrical": "EEE", "mechanical": "ME",
                "civil": "CE", "aiml": "AIML", "ai/ml": "AIML", "data science": "DS", "design": "Design"}
TITLE_NOISE = re.compile(r"^[\W_]*(?:📢|🚀|🔥|✨|🎉|⚡|🏆|💡)*\s*|[*_#~`]+", re.U)
SKILL_WORDS = ["Python", "JavaScript", "Java", "C++", "React", "Flask", "Node.js", "Machine Learning",
               "Deep Learning", "Data Analysis", "NLP", "SQL", "Cloud", "Android", "Flutter", "UI/UX",
               "Figma", "Blockchain", "IoT", "Cybersecurity", "DSA", "Pitching", "Public Speaking"]


def _field(value, confidence):
    return {"value": value, "confidence": confidence}


def _money_value(num, unit):
    """'1.5', 'lakh' -> 150000.0"""
    try:
        value = float(num.replace(",", ""))
    except (ValueError, AttributeError):
        return 0.0
    unit = (unit or "").lower()
    multiplier = {"k": 1e3, "l": 1e5, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "cr": 1e7, "crore": 1e7}.get(unit, 1)
    return value * multiplier


def extract_links(text):
    links = []
    for match in URL_RE.findall(text):
        url = match.rstrip(".,;!")
        if not url.lower().startswith("http"):
            url = "https://" + url
        if url not in links:
            links.append(url)
    return links


def extract_prize(text):
    best_amount, best_text, best_conf = 0.0, "", "low"
    for line in text.splitlines():
        lowered = line.lower()
        for m in MONEY_RE.finditer(line):
            num, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            amount = _money_value(num, unit)
            if "$" in m.group(0) or "usd" in m.group(0).lower():
                amount *= 83  # rough INR conversion so priority scoring compares like with like
            keyword = any(k in lowered for k in ("prize", "pool", "worth", "stipend", "reward", "win", "amount", "cash"))
            if amount > best_amount or (keyword and best_conf != "high"):
                best_amount, best_text = amount, m.group(0).strip()
                best_conf = "high" if keyword else "medium"
    return best_amount, best_text, best_conf


def extract_team(text):
    for regex, kind in TEAM_RE:
        m = regex.search(text)
        if not m:
            continue
        if kind == "solo":
            return 1, 1, "high"
        if kind == "max":
            return 1, int(m.group(1)), "high"
        if kind == "range":
            lo, hi = sorted((int(m.group(1)), int(m.group(2))))
            if hi <= 10:
                return lo, hi, "high"
        if kind == "exact":
            n = int(m.group(1))
            if n <= 10:
                return n, n, "medium"
    return 1, 1, "low"


TIME_RE = re.compile(r"\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm)", re.I)


def _parse_date(chunk, ref):
    # no time given -> end of day; a time given -> use it exactly (10 AM = 10:00, not 10:59)
    has_time = bool(TIME_RE.search(chunk))
    default = ref.replace(hour=0 if has_time else 23, minute=0 if has_time else 59, second=0, microsecond=0)
    try:
        dt = dparser.parse(chunk, fuzzy=True, dayfirst=True, default=default)
    except (ValueError, OverflowError, TypeError):
        return None
    # A date with no year that already passed most likely refers to next year
    if not re.search(r"\d{4}", chunk) and dt < ref.replace(hour=0, minute=0):
        dt = dt.replace(year=dt.year + 1)
    return dt


def extract_dates(text, ref=None):
    """Return (datetime, label, is_deadline) for every date mentioned. # CO2

    A date counts as the deadline when deadline words appear just before it on the same line,
    so one long WhatsApp line can hold both an event date and a registration deadline.
    """
    ref = ref or _now()
    found = []
    for line in text.splitlines():
        for m in DATE_LIKE.finditer(line):
            dt = _parse_date(m.group(0), ref)
            if not dt or abs((dt - ref).days) >= 800:
                continue
            before = line[:m.start()]
            near = before[-45:]
            sentence = re.split(r"[.!?]\s", before)[-1]
            label = line.strip() if len(line) < 60 else " ".join(sentence.split()[-4:])
            found.append((dt, label, bool(DEADLINE_WORDS.search(near))))
    return found


def guess_type(text):
    lowered = " " + text.lower() + " "
    scores = {t: sum(lowered.count(k) for k in kws) for t, kws in TYPE_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    total = sum(scores.values())
    if scores[best] == 0:
        return "competition", "low"
    share = scores[best] / total
    return best, "high" if share >= 0.6 and scores[best] >= 2 else "medium"


def guess_mode(text):
    lowered = text.lower()
    hits = {m: any(k in lowered for k in kws) for m, kws in MODE_KEYWORDS.items()}
    if hits["hybrid"] or (hits["online"] and hits["offline"]):
        return "hybrid", "medium"
    if hits["offline"]:
        return "offline", "high"
    if hits["online"]:
        return "online", "high"
    return "online", "low"


GREETING_RE = re.compile(r"^(?:hi|hey|hello|dear)\b[^!,.:]*[!,.:]\s*", re.I)
BANNER_RE = re.compile(r"\b(alert|announcement|attention|update|forwarded)\b", re.I)


def guess_title(text):
    for raw in text.splitlines():
        line = TITLE_NOISE.sub("", raw).strip(" :-|*•")
        line = re.sub(r"^(?:subject|fwd|fw|re)\s*:\s*", "", line, flags=re.I)
        line = GREETING_RE.sub("", line)  # "Hi all! Zeta Labs is hiring..." keeps the useful part
        if len(line) < 4 or URL_RE.fullmatch(line) or (BANNER_RE.search(line) and len(line) < 40):
            continue
        m = re.search(r"(?:presents?|announces?|invites? you to|welcome to|introducing)\s*[:\-]?\s*(.+)", line, re.I)
        if m:
            line = m.group(1)
        line = re.split(r"\s+[|–-]\s+|[.!]\s", line)[0].strip(" .!:")
        if len(line) > 90:
            line = line[:87].rsplit(" ", 1)[0] + "..."
        if len(line) >= 4:
            return line, "high" if any(w in line.lower() for kws in TYPE_KEYWORDS.values() for w in kws) else "medium"
    return "Untitled quest", "low"


WORD_YEARS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "final": 4, "pre-final": 3}
WORD_YEAR_RE = re.compile(r"\b(pre-final|first|second|third|fourth|final)[\s-]year", re.I)


def extract_eligibility(text):
    # work sentence by sentence so "for first-year students. Last date: ..." keeps the eligibility half
    sentences = [s.strip(" -•*") for s in re.split(r"(?<=[.!?])\s+|\n", text) if s.strip()]
    lines = [s for s in sentences if ELIGIBILITY_RE.search(s)]
    lines = [l for l in lines if not DEADLINE_WORDS.search(l) or "eligib" in l.lower()]
    joined = " ".join(lines)
    years = []
    m = YEAR_RE.search(joined)
    if m:
        years = sorted({int(g) for g in m.groups() if g})
        if len(years) == 2 and "to" in m.group(0).lower():
            years = list(range(years[0], years[1] + 1))
    if not years:
        years = sorted({WORD_YEARS[w.lower()] for w in WORD_YEAR_RE.findall(joined)})
    if re.search(r"all years|any year|all students", joined, re.I):
        years = []
    lowered = joined.lower()
    branches = sorted({v for k, v in BRANCH_WORDS.items() if re.search(rf"\b{re.escape(k)}\b", lowered)})
    if re.search(r"all branches|any branch|any discipline|all streams", lowered):
        branches = []
    conf = "high" if (years or branches) else ("medium" if lines else "low")
    return {"text": " ".join(lines)[:300], "years": years, "branches": branches}, conf


def extract_skills(text):
    lowered = text.lower()
    return [s for s in SKILL_WORDS if re.search(rf"(?<![a-z]){re.escape(s.lower())}(?![a-z])", lowered)]


def parse_briefing(text, ref=None):
    """Main entry point: returns a dict of fields with confidence levels. # CO2"""
    ref = ref or _now()
    text = (text or "").replace("\r\n", "\n").strip()
    result = {}
    title, conf = guess_title(text)
    result["title"] = _field(title, conf)
    qtype, conf = guess_type(text)
    result["type"] = _field(qtype, conf)

    dates = extract_dates(text, ref)
    future = sorted([d for d in dates if d[0] >= ref], key=lambda d: d[0])
    deadline_lines = [d for d in future if d[2]]
    if deadline_lines:
        deadline = deadline_lines[0][0]
        conf = "high"
    elif future:
        deadline = future[0][0]
        conf = "medium"
    else:
        deadline = ref.replace(hour=23, minute=59) + timedelta(days=14)
        conf = "low"
    result["deadline"] = _field(deadline.strftime("%Y-%m-%d %H:%M"), conf)
    rounds = []
    for dt, line, _ in future:
        if dt == deadline:
            continue
        name = re.sub(r"[:\-–|].*$", "", TITLE_NOISE.sub("", line)).strip(" ,;")[:50]
        if not name or name.lower() in ("date", "dates", "on", "when"):
            name = "Event day"
        rounds.append({"name": name, "deadline": dt.strftime("%Y-%m-%d %H:%M")})
    result["rounds"] = _field(rounds[:6], "medium" if rounds else "low")

    amount, prize_text, conf = extract_prize(text)
    result["prize_text"] = _field(prize_text, conf if prize_text else "low")
    result["prize_amount"] = _field(amount, conf if prize_text else "low")
    lo, hi, conf = extract_team(text)
    result["team_min"] = _field(lo, conf)
    result["team_max"] = _field(hi, conf)
    mode, conf = guess_mode(text)
    result["mode"] = _field(mode, conf)
    elig, conf = extract_eligibility(text)
    result["eligibility_text"] = _field(elig["text"], conf)
    result["eligible_years"] = _field(",".join(map(str, elig["years"])), conf if elig["years"] else "low")
    result["eligible_branches"] = _field(",".join(elig["branches"]), conf if elig["branches"] else "low")
    links = extract_links(text)
    result["link"] = _field(links[0] if links else "", "high" if links else "low")
    result["other_links"] = _field(links[1:], "medium")
    skills = extract_skills(text)
    result["skills"] = _field(skills, "medium" if skills else "low")
    org = re.search(r"(?:by|organi[sz]ed by|hosted by|from)\s+([A-Z][\w&.\- ]{2,40})", text)
    result["organizer"] = _field(org.group(1).strip(" .") if org else "", "medium" if org else "low")
    result["description"] = _field(text[:1000], "high")
    return result


def confidence_score(result):
    """Overall 0-100 confidence used for the meter on the preview."""
    weights = {"high": 1.0, "medium": 0.6, "low": 0.2}
    keys = ["title", "type", "deadline", "prize_text", "team_max", "mode", "link"]
    return round(100 * sum(weights[result[k]["confidence"]] for k in keys) / len(keys))
