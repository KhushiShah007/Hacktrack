"""Small date/text helpers used across services and templates."""
from datetime import datetime, date, timedelta

DT_FMT = "%Y-%m-%d %H:%M"
D_FMT = "%Y-%m-%d"


def now():
    return datetime.now().replace(second=0, microsecond=0)


def parse_dt(value):
    """Accept 'YYYY-MM-DD', 'YYYY-MM-DD HH:MM', 'YYYY-MM-DDTHH:MM' or datetime; return datetime or None."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, 23, 59)
    text = str(value).strip().replace("T", " ")
    for fmt in (DT_FMT, "%Y-%m-%d %H:%M:%S", D_FMT):
        try:
            dt = datetime.strptime(text, fmt)
            if fmt == D_FMT:
                dt = dt.replace(hour=23, minute=59)
            return dt
        except ValueError:
            continue
    return None


def fmt_dt(dt):
    dt = parse_dt(dt)
    return dt.strftime(DT_FMT) if dt else ""


def days_left(deadline, ref=None):
    """Fractional days until deadline (negative when overdue)."""
    dl = parse_dt(deadline)
    if not dl:
        return None
    ref = ref or now()
    return (dl - ref).total_seconds() / 86400


def countdown(deadline, ref=None):
    d = days_left(deadline, ref)
    if d is None:
        return "no date"
    if d < 0:
        late = -d
        return f"{int(late)}d overdue" if late >= 1 else f"{int(late * 24)}h overdue"
    if d < 1:
        return f"{int(d * 24)}h {int((d * 24 % 1) * 60)}m left"
    return f"{int(d)}d {int(d % 1 * 24)}h left"


def urgency_bucket(deadline, ref=None):
    """overdue / urgent (<48h) / week / later; drives card colours."""
    d = days_left(deadline, ref)
    if d is None:
        return "later"
    if d < 0:
        return "overdue"
    if d < 2:
        return "urgent"
    if d < 7:
        return "week"
    return "later"


def csv_list(text):
    return [p.strip() for p in (text or "").split(",") if p.strip()]


def pretty_date(value):
    dt = parse_dt(value)
    return dt.strftime("%d %b %Y") if dt else ""


def week_start(dt):
    d = parse_dt(dt).date()
    return d - timedelta(days=d.weekday())
