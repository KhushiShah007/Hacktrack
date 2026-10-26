"""CSV / JSON import and export of quests with a validation report (CO2: file handling + exceptions)."""
import csv
import io
import json
import logging

from ..constants import MODES, STATUSES, TYPES
from ..models import Opportunity
from ..utils import fmt_dt, parse_dt

log = logging.getLogger("hacktrack.io")

EXPORT_FIELDS = ["title", "type", "status", "deadline", "organizer", "link", "tags", "prize_text",
                 "prize_amount", "team_min", "team_max", "mode", "location", "eligible_years",
                 "eligible_branches", "eligibility_text", "effort_hours", "notes", "description"]
MAX_ROWS = 2000


def export_rows(opps):
    return [{f: getattr(o, f) for f in EXPORT_FIELDS} for o in opps]


def to_csv(opps):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EXPORT_FIELDS)
    writer.writeheader()
    writer.writerows(export_rows(opps))
    return buf.getvalue()


def to_json(opps):
    return json.dumps({"version": 1, "quests": export_rows(opps)}, indent=2, ensure_ascii=False)


def validate_row(raw):
    """Clean one record. Returns (clean_dict, errors). # CO2"""
    errors = []
    row = {k: (str(v).strip() if v is not None else "") for k, v in raw.items() if k}
    title = row.get("title", "")
    if not 2 <= len(title) <= 160:
        errors.append("title must be 2-160 characters")
    qtype = row.get("type", "").lower()
    if qtype not in TYPES:
        errors.append(f"type '{qtype}' must be one of {', '.join(TYPES)}")
    status = (row.get("status") or "interested").lower()
    if status not in STATUSES:
        errors.append(f"status '{status}' is not valid")
    deadline = parse_dt(row.get("deadline"))
    if not deadline:
        errors.append(f"deadline '{row.get('deadline', '')}' is not a date (use YYYY-MM-DD HH:MM)")
    mode = (row.get("mode") or "online").lower()
    if mode not in MODES:
        errors.append(f"mode '{mode}' must be online/offline/hybrid")
    numbers = {}
    for key, default in (("prize_amount", 0.0), ("team_min", 1), ("team_max", 1), ("effort_hours", 0)):
        try:
            value = row.get(key) or default
            numbers[key] = float(value) if key == "prize_amount" else int(float(value))
            if numbers[key] < 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"{key} '{row.get(key)}' must be a non-negative number")
    if not errors and numbers["team_max"] < numbers["team_min"]:
        errors.append("team_max must be >= team_min")
    clean = {**row, **numbers, "type": qtype, "status": status, "mode": mode,
             "deadline": fmt_dt(deadline) if deadline else ""}
    return clean, errors


def import_records(db, user_id, records):
    """Validate and insert; returns report {'created', 'errors': [(row, [msgs])]}. # CO2 # CO3"""
    report = {"created": 0, "errors": [], "total": 0}
    for i, raw in enumerate(records, start=2):  # row 1 is the CSV header
        if report["total"] >= MAX_ROWS:
            report["errors"].append((i, [f"stopped after {MAX_ROWS} rows"]))
            break
        report["total"] += 1
        if not isinstance(raw, dict):
            report["errors"].append((i, ["record is not an object"]))
            continue
        clean, errors = validate_row(raw)
        if errors:
            report["errors"].append((i, errors))
            log.warning("import row %s rejected: %s", i, "; ".join(errors))
            continue
        try:
            fields = {k: v for k, v in clean.items() if k in EXPORT_FIELDS}
            opp = Opportunity.create(clean["type"], user_id=user_id, source="import", **fields)
            opp.save(db)
            report["created"] += 1
        except Exception as exc:  # sqlite CHECK failures etc. are reported, not raised
            report["errors"].append((i, [f"database rejected row: {exc}"]))
            log.exception("import row %s failed", i)
    log.info("import for user %s: %s created, %s rejected", user_id, report["created"], len(report["errors"]))
    return report


def parse_upload(filename, data):
    """Decode an uploaded CSV/JSON file into a list of dict records. Raises ValueError with a friendly message."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        log.warning("upload %s is not UTF-8: %s", filename, exc)
        raise ValueError("File must be UTF-8 text (CSV or JSON).") from exc
    name = filename.lower()
    try:
        if name.endswith(".json"):
            payload = json.loads(text)
            records = payload.get("quests", []) if isinstance(payload, dict) else payload
            if not isinstance(records, list):
                raise ValueError("JSON must be a list of quests or {\"quests\": [...]}")
            return records
        if name.endswith(".csv"):
            reader = csv.DictReader(io.StringIO(text))
            if not reader.fieldnames or "title" not in reader.fieldnames:
                raise ValueError("CSV needs a header row with at least title,type,deadline")
            return list(reader)
    except json.JSONDecodeError as exc:
        log.warning("bad JSON upload %s: %s", filename, exc)
        raise ValueError(f"JSON is invalid at line {exc.lineno}: {exc.msg}") from exc
    except csv.Error as exc:
        log.warning("bad CSV upload %s: %s", filename, exc)
        raise ValueError(f"CSV could not be read: {exc}") from exc
    raise ValueError("Only .csv and .json files can be imported.")
