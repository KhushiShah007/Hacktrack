"""Game vocabulary and static tables shared by the whole app."""

TYPES = ["hackathon", "competition", "internship", "scholarship", "workshop", "research"]
TYPE_LABELS = {
    "hackathon": "Hackathon",
    "competition": "Competition",
    "internship": "Internship",
    "scholarship": "Scholarship",
    "workshop": "Workshop",
    "research": "Research Program",
}

STATUSES = ["interested", "preparing", "registered", "submitted", "shortlisted", "won", "rejected"]
STATUS_LABELS = {
    "interested": "Interested",
    "preparing": "Preparing",
    "registered": "Registered",
    "submitted": "Submitted",
    "shortlisted": "Shortlisted",
    "won": "Won / Selected",
    "rejected": "Rejected / Missed",
}
OPEN_STATUSES = ("interested", "preparing", "registered")
DONE_STATUSES = ("submitted", "shortlisted", "won", "rejected")

MODES = ["online", "offline", "hybrid"]
ROUND_STATUSES = ["pending", "cleared", "failed", "skipped"]
TASK_STATUSES = ["todo", "doing", "done"]
ASSET_CATEGORIES = ["github", "demo", "ppt", "report", "certificate", "image", "other"]

AVATAR_LOOKS = {
    "knight": "Pixel Knight",
    "coder": "Code Witch",
    "astro": "Astro Cadet",
    "ranger": "Forest Ranger",
}

BRANCHES = ["CSE", "IT", "ECE", "EEE", "ME", "CE", "AIML", "DS", "Design", "BBA", "Other"]

SKILL_CATALOG = [
    ("Python", "code"), ("JavaScript", "code"), ("Java", "code"), ("C++", "code"),
    ("React", "web"), ("Flask", "web"), ("Node.js", "web"), ("HTML/CSS", "web"),
    ("Machine Learning", "ai"), ("Deep Learning", "ai"), ("Data Analysis", "ai"), ("NLP", "ai"),
    ("SQL", "data"), ("Cloud", "infra"), ("DevOps", "infra"), ("Android", "mobile"),
    ("Flutter", "mobile"), ("UI/UX", "design"), ("Figma", "design"), ("Public Speaking", "soft"),
    ("Pitching", "soft"), ("Research Writing", "soft"), ("DSA", "code"), ("Cybersecurity", "infra"),
    ("IoT", "hardware"), ("Blockchain", "web"), ("Video Editing", "design"), ("Finance", "domain"),
]

# code, name, description, sprite icon
BADGES = [
    ("first_quest", "Quest Accepted", "Added your first quest.", "pin"),
    ("first_submission", "First Submission", "Submitted something for the first time.", "coin"),
    ("finalist", "Finalist", "Got shortlisted for a final round.", "star"),
    ("winner", "Winner", "Won a quest or got selected.", "trophy"),
    ("five_in_month", "5 Events in a Month", "Registered for 5 quests in one month.", "mushroom"),
    ("streak_7", "7-Day Streak", "Earned XP seven days in a row.", "flame"),
    ("team_player", "Team Player", "Joined or formed a party.", "heart"),
    ("scribe", "Scribe", "Wrote 3 Training Log entries.", "scroll"),
    ("planner", "Master Planner", "Generated a back-plan and finished every milestone.", "door"),
    ("trophy_hunter", "Trophy Hunter", "Reached the trophy at the end of a Quest Roadmap.", "trophy"),
    ("side_quester", "Side Quester", "Shared a Side Quest with your college.", "cat"),
    ("collector", "Collector", "Stored 5 items in your Inventory.", "coin"),
]

LEVEL_TITLES = [
    (1, "Rookie"),
    (3, "Challenger"),
    (6, "Strategist"),
    (10, "Champion"),
    (15, "Legend"),
]

XP_RULES = {
    "add_quest": 10,
    "finish_milestone": 15,
    "clear_round": 25,
    "register": 15,
    "submit": 40,
    "shortlist": 50,
    "win": 100,
    "journal": 20,
    "feed_post": 10,
    "trophy": 150,
    "join_party": 20,
    "add_asset": 5,
}
