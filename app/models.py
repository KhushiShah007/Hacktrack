"""Domain classes (CO1): inheritance + polymorphism for quest types, plus thin raw-SQL persistence (CO3).

Every quest type is a subclass of `Opportunity` and overrides `stages()`, `effort_estimate()` and
`describe()`. `Opportunity.from_row()` picks the right subclass from a registry filled by
`__init_subclass__`, so the rest of the app never needs `if type == ...` chains.
"""
import json
from dataclasses import dataclass, field
from functools import reduce

from .constants import STATUS_LABELS, TYPE_LABELS, DONE_STATUSES, OPEN_STATUSES, AVATAR_LOOKS
from .utils import countdown, csv_list, days_left, now, parse_dt, urgency_bucket, fmt_dt

OPP_COLUMNS = [
    "type", "title", "organizer", "description", "link", "tags", "prize_text", "prize_amount",
    "team_min", "team_max", "mode", "location", "eligible_years", "eligible_branches",
    "eligible_colleges", "eligibility_text", "start_date", "deadline", "status", "effort_hours",
    "notes", "extra_json", "source",
]


class Opportunity:
    """Base class for every quest. # CO1"""

    type_key = "generic"
    icon = "pin"
    base_effort = 20
    extra_fields = []          # (key, label) pairs shown only for this type
    _registry = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Opportunity._registry[cls.type_key] = cls

    def __init__(self, **data):
        self.id = data.get("id")
        self.user_id = data.get("user_id")
        self.type = self.type_key
        self.title = data.get("title", "")
        self.organizer = data.get("organizer", "") or ""
        self.description = data.get("description", "") or ""
        self.link = data.get("link", "") or ""
        self.tags = data.get("tags", "") or ""
        self.prize_text = data.get("prize_text", "") or ""
        self.prize_amount = float(data.get("prize_amount") or 0)
        self.team_min = int(data.get("team_min") or 1)
        self.team_max = int(data.get("team_max") or self.team_min)
        self.mode = data.get("mode") or "online"
        self.location = data.get("location", "") or ""
        self.eligible_years = data.get("eligible_years", "") or ""
        self.eligible_branches = data.get("eligible_branches", "") or ""
        self.eligible_colleges = data.get("eligible_colleges", "") or ""
        self.eligibility_text = data.get("eligibility_text", "") or ""
        self.start_date = data.get("start_date")
        self.deadline = fmt_dt(data.get("deadline")) or fmt_dt(now())
        self.status = data.get("status") or "interested"
        self.effort_hours = int(data.get("effort_hours") or 0)
        self.notes = data.get("notes", "") or ""
        extra = data.get("extra_json") or data.get("extra") or {}
        self.extra = json.loads(extra) if isinstance(extra, str) else dict(extra)
        self.source = data.get("source") or "manual"
        self.registered_at = data.get("registered_at")
        self.submitted_at = data.get("submitted_at")
        self.result_at = data.get("result_at")
        self.trophy_claimed = int(data.get("trophy_claimed") or 0)
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")

    # ----- factory -----
    @classmethod
    def class_for(cls, type_key):
        return cls._registry.get(type_key, Hackathon)

    @classmethod
    def create(cls, type_key, **data):
        return cls.class_for(type_key)(**data)

    @classmethod
    def from_row(cls, row):
        data = dict(row)
        return cls.create(data.get("type"), **data)

    # ----- polymorphic API (overridden by subclasses) -----
    def stages(self):
        return ["Register", "Participate", "Result"]

    def effort_estimate(self):
        """Hours of work; an explicit value from the user always wins."""
        return self.effort_hours or self.base_effort

    def describe(self):
        return f"{self.title} ({self.label})"

    # ----- shared behaviour -----
    @property
    def label(self):
        return TYPE_LABELS.get(self.type_key, "Opportunity")

    @property
    def status_label(self):
        if self.status == "won" and self.type in ("internship", "research", "scholarship"):
            return "Selected"
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def tag_list(self):
        return csv_list(self.tags)

    @property
    def is_done(self):
        return self.status in DONE_STATUSES

    @property
    def is_open(self):
        return self.status in OPEN_STATUSES

    def days_left(self, ref=None):
        return days_left(self.deadline, ref)

    def countdown(self, ref=None):
        return countdown(self.deadline, ref)

    def urgency(self, ref=None):
        if self.is_done:
            return "done"
        return urgency_bucket(self.deadline, ref)

    def team_text(self):
        if self.team_max <= 1:
            return "Solo"
        if self.team_min == self.team_max:
            return f"Team of {self.team_max}"
        return f"Team {self.team_min}-{self.team_max}"

    def to_dict(self):
        data = {c: getattr(self, c) for c in OPP_COLUMNS if c != "extra_json"}
        data.update(id=self.id, extra=self.extra, label=self.label, status_label=self.status_label,
                    countdown=self.countdown(), urgency=self.urgency(),
                    effort_estimate=self.effort_estimate(), stages=self.stages())
        return data

    def column_values(self):
        values = []
        for col in OPP_COLUMNS:
            if col == "extra_json":
                values.append(json.dumps(self.extra))
            else:
                values.append(getattr(self, col))
        return values

    # ----- persistence (raw SQL, CO3) -----
    def save(self, db):
        """INSERT a new quest or UPDATE an existing one. # CO3"""
        if self.id:
            sets = ", ".join(f"{c} = ?" for c in OPP_COLUMNS)
            db.execute(
                f"UPDATE opportunities SET {sets}, updated_at = datetime('now','localtime') "
                "WHERE id = ? AND user_id = ?",
                (*self.column_values(), self.id, self.user_id),
            )
        else:
            cols = ", ".join(["user_id", *OPP_COLUMNS])
            marks = ", ".join("?" * (len(OPP_COLUMNS) + 1))
            cur = db.execute(f"INSERT INTO opportunities ({cols}) VALUES ({marks})",
                             (self.user_id, *self.column_values()))
            self.id = cur.lastrowid
        db.commit()
        return self.id

    @classmethod
    def get(cls, db, opp_id, user_id):
        row = db.execute("SELECT * FROM opportunities WHERE id = ? AND user_id = ?",
                         (opp_id, user_id)).fetchone()
        return cls.from_row(row) if row else None

    @classmethod
    def for_user(cls, db, user_id, where="", args=(), order="deadline ASC"):
        sql = f"SELECT * FROM opportunities WHERE user_id = ? {where} ORDER BY {order}"
        return [cls.from_row(r) for r in db.execute(sql, (user_id, *args)).fetchall()]

    def required_skills(self, db):
        rows = db.execute(
            "SELECT s.name, os.importance FROM opportunity_skills os JOIN skills s ON s.id = os.skill_id "
            "WHERE os.opportunity_id = ? ORDER BY os.importance DESC, s.name", (self.id,)).fetchall()
        return {r["name"]: r["importance"] for r in rows}

    def rounds(self, db):
        rows = db.execute("SELECT * FROM rounds WHERE opportunity_id = ? ORDER BY deadline, seq",
                          (self.id,)).fetchall()
        return [Round.from_row(r) for r in rows]

    def milestones(self, db):
        rows = db.execute("SELECT * FROM milestones WHERE opportunity_id = ? ORDER BY due_date, seq",
                          (self.id,)).fetchall()
        return [Milestone.from_row(r) for r in rows]

    def __repr__(self):
        return f"<{type(self).__name__} #{self.id} {self.title!r}>"


class Hackathon(Opportunity):
    type_key = "hackathon"
    icon = "laptop"
    base_effort = 36
    extra_fields = [("theme", "Theme / track"), ("platform", "Platform (Devfolio, Unstop...)")]

    def stages(self):
        return ["PPT Screening", "Prototype", "Finals", "Result"]

    def effort_estimate(self):
        # smaller teams carry more of the build, so they need more hours each
        if self.effort_hours:
            return self.effort_hours
        return self.base_effort + (12 if self.team_max <= 2 else 0)

    def describe(self):
        prize = f" with {self.prize_text} in prizes" if self.prize_text else ""
        return f"{self.team_text()} hackathon by {self.organizer or 'an organiser'}{prize}."


class Competition(Opportunity):
    type_key = "competition"
    icon = "sword"
    base_effort = 20
    extra_fields = [("domain", "Domain (coding, case study, design...)"), ("platform", "Platform")]

    def stages(self):
        return ["Registration", "Qualifier", "Semi-final", "Final"]

    def effort_estimate(self):
        return self.effort_hours or self.base_effort + 4 * max(len(self.tag_list) - 1, 0)

    def describe(self):
        domain = self.extra.get("domain") or "open"
        return f"A {domain} competition by {self.organizer or 'an organiser'}, {self.mode}."


class Internship(Opportunity):
    type_key = "internship"
    icon = "briefcase"
    base_effort = 15
    extra_fields = [("company", "Company"), ("role", "Role"), ("stipend", "Stipend / month"),
                    ("duration", "Duration")]

    def stages(self):
        return ["Applied", "OA", "Interview", "Offer"]

    def effort_estimate(self):
        # interview prep scales with the number of hiring stages
        return self.effort_hours or self.base_effort + 3 * len(self.stages())

    def describe(self):
        role = self.extra.get("role") or "Intern"
        company = self.extra.get("company") or self.organizer or "a company"
        stipend = f", stipend {self.extra['stipend']}" if self.extra.get("stipend") else ""
        return f"{role} at {company}{stipend}."


class Scholarship(Opportunity):
    type_key = "scholarship"
    icon = "scroll"
    base_effort = 8
    extra_fields = [("provider", "Provider"), ("amount", "Amount"), ("renewable", "Renewable? (yes/no)")]

    def stages(self):
        return ["Application", "Documents", "Interview", "Award"]

    def effort_estimate(self):
        return self.effort_hours or self.base_effort + (4 if "essay" in self.description.lower() else 0)

    def describe(self):
        amount = self.extra.get("amount") or self.prize_text or "an award"
        return f"Scholarship worth {amount} from {self.extra.get('provider') or self.organizer or 'a provider'}."


class Workshop(Opportunity):
    type_key = "workshop"
    icon = "wrench"
    base_effort = 6
    extra_fields = [("speaker", "Speaker / host"), ("certificate", "Certificate? (yes/no)")]

    def stages(self):
        return ["Register", "Attend", "Assignment", "Certificate"]

    def describe(self):
        cert = " with certificate" if str(self.extra.get("certificate", "")).lower().startswith("y") else ""
        return f"{self.mode.title()} workshop{cert} hosted by {self.extra.get('speaker') or self.organizer or 'TBA'}."


class ResearchProgram(Opportunity):
    type_key = "research"
    icon = "flask"
    base_effort = 25
    extra_fields = [("lab", "Lab / institute"), ("professor", "Professor / guide"), ("duration", "Duration")]

    def stages(self):
        return ["Proposal", "Shortlist", "Interview", "Offer"]

    def effort_estimate(self):
        return self.effort_hours or self.base_effort + (10 if "proposal" in self.description.lower() else 0)

    def describe(self):
        return f"Research program at {self.extra.get('lab') or self.organizer or 'a lab'}."


@dataclass
class Round:
    """One stage of a quest with its own deadline and result. # CO1"""
    id: int = None
    opportunity_id: int = None
    seq: int = 1
    name: str = ""
    deadline: str = ""
    status: str = "pending"
    result_note: str = ""

    @classmethod
    def from_row(cls, row):
        d = dict(row)
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})

    @property
    def is_done(self):
        return self.status in ("cleared", "skipped")

    def countdown(self):
        return countdown(self.deadline)


@dataclass
class Milestone:
    """Back-plan node; children make a tree whose progress is computed recursively. # CO1"""
    id: int = None
    opportunity_id: int = None
    parent_id: int = None
    title: str = ""
    phase: str = ""
    due_date: str = ""
    seq: int = 0
    done: int = 0
    done_at: str = None
    children: list = field(default_factory=list)

    @classmethod
    def from_row(cls, row):
        d = dict(row)
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__ if k != "children"})

    @staticmethod
    def build_tree(milestones):
        by_id = {m.id: m for m in milestones}
        roots = []
        for m in milestones:
            m.children = []
        for m in milestones:
            (by_id[m.parent_id].children if m.parent_id in by_id else roots).append(m)
        return roots

    def leaf_counts(self):
        """Recursively count (done, total) leaves under this node. # CO1 recursion"""
        if not self.children:
            return (1 if self.done else 0, 1)
        return reduce(lambda acc, c: (acc[0] + c[0], acc[1] + c[1]),
                      (child.leaf_counts() for child in self.children), (0, 0))

    def progress(self):
        done, total = self.leaf_counts()
        return round(100 * done / total) if total else 0


@dataclass
class User:
    """A player. # CO1"""
    id: int = None
    username: str = ""
    email: str = ""
    display_name: str = ""
    avatar_look: str = "knight"
    college: str = ""
    year: int = None
    branch: str = ""
    bio: str = ""
    interests: str = ""
    is_public: int = 1
    onboarded: int = 0
    api_token: str = None
    telegram_chat_id: str = ""
    email_reminders: int = 0
    created_at: str = ""

    @classmethod
    def from_row(cls, row):
        d = dict(row)
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})

    @classmethod
    def get(cls, db, user_id):
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return cls.from_row(row) if row else None

    @classmethod
    def by_username(cls, db, username):
        row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return cls.from_row(row) if row else None

    @property
    def name(self):
        return self.display_name or self.username

    @property
    def look_label(self):
        return AVATAR_LOOKS.get(self.avatar_look, "Player")

    def skills(self, db):
        rows = db.execute(
            "SELECT s.name, us.proficiency FROM user_skills us JOIN skills s ON s.id = us.skill_id "
            "WHERE us.user_id = ? ORDER BY us.proficiency DESC, s.name", (self.id,)).fetchall()
        return {r["name"]: r["proficiency"] for r in rows}

    def xp_total(self, db):
        return db.execute("SELECT COALESCE(SUM(points), 0) FROM xp_events WHERE user_id = ?",
                          (self.id,)).fetchone()[0]


@dataclass
class Member:
    """A user inside a team, with their skills for skill-matching. # CO1"""
    user_id: int
    username: str
    display_name: str = ""
    role: str = "member"
    status: str = "active"
    avatar_look: str = "knight"
    skills: dict = field(default_factory=dict)

    @property
    def name(self):
        return self.display_name or self.username


@dataclass
class Team:
    """A party of players working on a quest. # CO1"""
    id: int = None
    name: str = ""
    owner_id: int = None
    opportunity_id: int = None
    created_at: str = ""
    members: list = field(default_factory=list)

    @classmethod
    def from_row(cls, row):
        d = dict(row)
        return cls(**{k: d.get(k) for k in ("id", "name", "owner_id", "opportunity_id", "created_at")})

    def load_members(self, db):
        rows = db.execute(
            "SELECT u.id, u.username, u.display_name, u.avatar_look, tm.role, tm.status "
            "FROM team_members tm JOIN users u ON u.id = tm.user_id WHERE tm.team_id = ? "
            "ORDER BY tm.status, u.username", (self.id,)).fetchall()
        self.members = []
        for r in rows:
            skills = User(id=r["id"]).skills(db)
            self.members.append(Member(r["id"], r["username"], r["display_name"], r["role"],
                                       r["status"], r["avatar_look"], skills))
        return self.members

    @property
    def active_members(self):
        return list(filter(lambda m: m.status == "active", self.members))


@dataclass
class Badge:
    """An unlockable achievement. # CO1"""
    id: int = None
    code: str = ""
    name: str = ""
    description: str = ""
    icon: str = "star"
    unlocked_at: str = None

    @classmethod
    def from_row(cls, row):
        d = dict(row)
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})

    @property
    def unlocked(self):
        return self.unlocked_at is not None


def deadline_sort_key(opp):
    dl = parse_dt(opp.deadline)
    return dl or now()
