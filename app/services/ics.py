"""Hand-written iCalendar (.ics) export for quests, rounds and milestones."""
from datetime import timedelta

from ..utils import parse_dt, now as _now


def _esc(text):
    return (str(text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n"))


def _fold(line):
    """RFC 5545 lines must be folded at 75 octets."""
    out = []
    while len(line) > 74:
        out.append(line[:74])
        line = " " + line[74:]
    out.append(line)
    return "\r\n".join(out)


def build_ics(events, cal_name="HackTrack Quests"):
    """events: dicts with uid, title, when, description, url, alarm (bool). # CO2"""
    stamp = _now().strftime("%Y%m%dT%H%M%S")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//HackTrack//Quest Calendar//EN",
             "CALSCALE:GREGORIAN", f"X-WR-CALNAME:{_esc(cal_name)}"]
    for e in events:
        start = parse_dt(e["when"])
        if not start:
            continue
        end = start + timedelta(minutes=30)
        lines += [
            "BEGIN:VEVENT",
            f"UID:{e['uid']}@hacktrack",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}",
            _fold(f"SUMMARY:{_esc(e['title'])}"),
            _fold(f"DESCRIPTION:{_esc(e.get('description', ''))}"),
        ]
        if e.get("url"):
            lines.append(_fold(f"URL:{e['url']}"))
        if e.get("alarm", True):
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", "TRIGGER:-P1D", _fold(f"DESCRIPTION:{_esc(e['title'])}"), "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def quest_events(opp, rounds, milestones):
    events = [{"uid": f"quest-{opp.id}", "title": f"[{opp.label}] {opp.title} - deadline",
               "when": opp.deadline, "description": opp.describe(), "url": opp.link}]
    events += [{"uid": f"round-{r.id}", "title": f"{opp.title}: {r.name}", "when": r.deadline,
                "description": f"Round {r.seq} ({r.status})", "url": opp.link} for r in rounds]
    events += [{"uid": f"milestone-{m.id}", "title": f"{opp.title}: {m.title}", "when": m.due_date,
                "description": f"Back-plan milestone ({m.phase})", "alarm": False} for m in milestones if not m.done]
    return events
