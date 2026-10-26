-- =====================================================================
-- HackTrack schema (CO3: raw SQLite DDL)
-- Every table uses explicit foreign keys, CHECK constraints and indexes.
-- Run through app.db.init_db(); `CREATE ... IF NOT EXISTS` makes it idempotent.
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------- players ----------
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE COLLATE NOCASE
                    CHECK (length(username) BETWEEN 3 AND 30),
    email           TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash   TEXT    NOT NULL,
    display_name    TEXT    NOT NULL DEFAULT '',
    avatar_look     TEXT    NOT NULL DEFAULT 'knight'
                    CHECK (avatar_look IN ('knight', 'coder', 'astro', 'ranger')),
    college         TEXT    NOT NULL DEFAULT '',
    year            INTEGER CHECK (year IS NULL OR year BETWEEN 1 AND 6),
    branch          TEXT    NOT NULL DEFAULT '',
    bio             TEXT    NOT NULL DEFAULT '',
    interests       TEXT    NOT NULL DEFAULT '',
    is_public       INTEGER NOT NULL DEFAULT 1 CHECK (is_public IN (0, 1)),
    onboarded       INTEGER NOT NULL DEFAULT 0 CHECK (onboarded IN (0, 1)),
    api_token       TEXT    UNIQUE,
    telegram_chat_id TEXT   NOT NULL DEFAULT '',
    email_reminders INTEGER NOT NULL DEFAULT 0 CHECK (email_reminders IN (0, 1)),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS skills (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    category  TEXT NOT NULL DEFAULT 'general'
);

CREATE TABLE IF NOT EXISTS user_skills (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_id    INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    proficiency INTEGER NOT NULL DEFAULT 3 CHECK (proficiency BETWEEN 1 AND 5),
    PRIMARY KEY (user_id, skill_id)
);

-- ---------- quests (opportunities) ----------
CREATE TABLE IF NOT EXISTS opportunities (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type              TEXT    NOT NULL CHECK (type IN
                      ('hackathon', 'competition', 'internship', 'scholarship', 'workshop', 'research')),
    title             TEXT    NOT NULL CHECK (length(title) BETWEEN 2 AND 160),
    organizer         TEXT    NOT NULL DEFAULT '',
    description       TEXT    NOT NULL DEFAULT '',
    link              TEXT    NOT NULL DEFAULT '',
    tags              TEXT    NOT NULL DEFAULT '',
    prize_text        TEXT    NOT NULL DEFAULT '',
    prize_amount      REAL    NOT NULL DEFAULT 0 CHECK (prize_amount >= 0),
    team_min          INTEGER NOT NULL DEFAULT 1 CHECK (team_min >= 1),
    team_max          INTEGER NOT NULL DEFAULT 1,
    mode              TEXT    NOT NULL DEFAULT 'online' CHECK (mode IN ('online', 'offline', 'hybrid')),
    location          TEXT    NOT NULL DEFAULT '',
    eligible_years    TEXT    NOT NULL DEFAULT '',   -- CSV e.g. "2,3,4"; empty = any
    eligible_branches TEXT    NOT NULL DEFAULT '',   -- CSV e.g. "CSE,IT"; empty = any
    eligible_colleges TEXT    NOT NULL DEFAULT '',   -- CSV; empty = any
    eligibility_text  TEXT    NOT NULL DEFAULT '',
    start_date        TEXT,
    deadline          TEXT    NOT NULL,             -- 'YYYY-MM-DD HH:MM'
    status            TEXT    NOT NULL DEFAULT 'interested' CHECK (status IN
                      ('interested', 'preparing', 'registered', 'submitted', 'shortlisted', 'won', 'rejected')),
    effort_hours      INTEGER NOT NULL DEFAULT 0 CHECK (effort_hours >= 0),
    notes             TEXT    NOT NULL DEFAULT '',
    extra_json        TEXT    NOT NULL DEFAULT '{}', -- type-specific fields
    source            TEXT    NOT NULL DEFAULT 'manual',
    registered_at     TEXT,
    submitted_at      TEXT,
    result_at         TEXT,
    trophy_claimed    INTEGER NOT NULL DEFAULT 0 CHECK (trophy_claimed IN (0, 1)),
    created_at        TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    CHECK (team_max >= team_min)
);
CREATE INDEX IF NOT EXISTS idx_opp_user_deadline ON opportunities(user_id, deadline);
CREATE INDEX IF NOT EXISTS idx_opp_user_status   ON opportunities(user_id, status);
CREATE INDEX IF NOT EXISTS idx_opp_type          ON opportunities(type);

CREATE TABLE IF NOT EXISTS opportunity_skills (
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    skill_id       INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    importance     INTEGER NOT NULL DEFAULT 2 CHECK (importance BETWEEN 1 AND 3),
    PRIMARY KEY (opportunity_id, skill_id)
);

CREATE TABLE IF NOT EXISTS rounds (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    seq            INTEGER NOT NULL DEFAULT 1 CHECK (seq >= 1),
    name           TEXT    NOT NULL,
    deadline       TEXT    NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending', 'cleared', 'failed', 'skipped')),
    result_note    TEXT    NOT NULL DEFAULT '',
    created_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_rounds_opp ON rounds(opportunity_id, deadline);

-- milestones form a tree (parent_id) built by the recursive back-planner
CREATE TABLE IF NOT EXISTS milestones (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    parent_id      INTEGER REFERENCES milestones(id) ON DELETE CASCADE,
    title          TEXT    NOT NULL,
    phase          TEXT    NOT NULL DEFAULT '',
    due_date       TEXT    NOT NULL,
    seq            INTEGER NOT NULL DEFAULT 0,
    done           INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1)),
    done_at        TEXT
);
CREATE INDEX IF NOT EXISTS idx_milestones_opp ON milestones(opportunity_id, due_date);

-- ---------- party (teams) ----------
CREATE TABLE IF NOT EXISTS teams (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL CHECK (length(name) BETWEEN 2 AND 60),
    owner_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE SET NULL,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS team_members (
    team_id   INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role      TEXT    NOT NULL DEFAULT 'member',
    status    TEXT    NOT NULL DEFAULT 'invited' CHECK (status IN ('invited', 'active')),
    joined_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    PRIMARY KEY (team_id, user_id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    round_id    INTEGER REFERENCES rounds(id) ON DELETE SET NULL,
    assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    title       TEXT    NOT NULL CHECK (length(title) BETWEEN 1 AND 160),
    status      TEXT    NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'doing', 'done')),
    due_date    TEXT,
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_tasks_team ON tasks(team_id, status);

CREATE TABLE IF NOT EXISTS team_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id    INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    message    TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ---------- inventory, training log ----------
CREATE TABLE IF NOT EXISTS assets (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind           TEXT    NOT NULL CHECK (kind IN ('link', 'file')),
    category       TEXT    NOT NULL DEFAULT 'other'
                   CHECK (category IN ('github', 'demo', 'ppt', 'report', 'certificate', 'image', 'other')),
    label          TEXT    NOT NULL,
    url            TEXT    NOT NULL DEFAULT '',
    stored_name    TEXT    NOT NULL DEFAULT '',
    original_name  TEXT    NOT NULL DEFAULT '',
    mime           TEXT    NOT NULL DEFAULT '',
    size_bytes     INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes BETWEEN 0 AND 5242880),
    created_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_assets_opp ON assets(opportunity_id);

CREATE TABLE IF NOT EXISTS journal_entries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE SET NULL,
    title          TEXT    NOT NULL,
    what_worked    TEXT    NOT NULL DEFAULT '',
    what_failed    TEXT    NOT NULL DEFAULT '',
    lessons        TEXT    NOT NULL DEFAULT '',
    rating         INTEGER NOT NULL DEFAULT 3 CHECK (rating BETWEEN 1 AND 5),
    tags           TEXT    NOT NULL DEFAULT '',
    created_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_journal_user ON journal_entries(user_id, created_at);

-- ---------- achievements ----------
CREATE TABLE IF NOT EXISTS badges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    icon        TEXT NOT NULL DEFAULT 'star'
);

CREATE TABLE IF NOT EXISTS user_badges (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    badge_id    INTEGER NOT NULL REFERENCES badges(id) ON DELETE CASCADE,
    unlocked_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    seen        INTEGER NOT NULL DEFAULT 0 CHECK (seen IN (0, 1)),
    PRIMARY KEY (user_id, badge_id)
);

CREATE TABLE IF NOT EXISTS xp_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action     TEXT    NOT NULL,
    points     INTEGER NOT NULL CHECK (points >= 0),
    ref        TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_xp_user_time ON xp_events(user_id, created_at);

-- ---------- side quests (college feed) ----------
CREATE TABLE IF NOT EXISTS feed_posts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    college     TEXT    NOT NULL DEFAULT '',
    type        TEXT    NOT NULL CHECK (type IN
                ('hackathon', 'competition', 'internship', 'scholarship', 'workshop', 'research')),
    title       TEXT    NOT NULL CHECK (length(title) BETWEEN 2 AND 160),
    description TEXT    NOT NULL DEFAULT '',
    link        TEXT    NOT NULL DEFAULT '',
    deadline    TEXT    NOT NULL,
    prize_text  TEXT    NOT NULL DEFAULT '',
    tags        TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS feed_votes (
    post_id INTEGER NOT NULL REFERENCES feed_posts(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    value   INTEGER NOT NULL DEFAULT 1 CHECK (value = 1),
    PRIMARY KEY (post_id, user_id)
);

-- ---------- notifications ----------
CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind       TEXT    NOT NULL DEFAULT 'info' CHECK (kind IN ('info', 'reminder', 'badge', 'party', 'level')),
    message    TEXT    NOT NULL,
    link       TEXT    NOT NULL DEFAULT '',
    dedupe_key TEXT,
    is_read    INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0, 1)),
    created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (user_id, dedupe_key)
);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read);
