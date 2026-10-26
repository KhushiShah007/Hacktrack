"""Insights Dashboard (CO4): pandas aggregation, numpy statistics, matplotlib fallback charts."""
import io
import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd

from ..constants import TYPE_LABELS
from . import xp as xp_service

log = logging.getLogger("hacktrack.insights")
SUCCESS = ("won", "shortlisted")
RESOLVED = ("won", "shortlisted", "rejected")
PALETTE = ["#ff4fb4", "#3df58a", "#4fd8ff", "#ffd23f", "#b48cff", "#ff8a3d"]


def load_frames(db, user_id):
    quests = pd.read_sql_query(
        "SELECT id, type, status, deadline, prize_amount, registered_at, submitted_at, created_at "
        "FROM opportunities WHERE user_id = ?", db, params=(user_id,))
    events = pd.read_sql_query("SELECT action, points, created_at FROM xp_events WHERE user_id = ?",
                               db, params=(user_id,))
    for col in ("deadline", "registered_at", "submitted_at", "created_at"):
        quests[col] = pd.to_datetime(quests[col], errors="coerce")
    events["created_at"] = pd.to_datetime(events["created_at"], errors="coerce")
    return quests, events


def build_insights(db, user_id, today=None):
    """Return every number the Insights page needs, JSON-serialisable. # CO4"""
    today = today or date.today()
    quests, events = load_frames(db, user_id)
    out = {"total": int(len(quests)), "empty": quests.empty}

    by_type = quests.groupby("type").size().sort_values(ascending=False)
    out["by_type"] = {TYPE_LABELS[k]: int(v) for k, v in by_type.items()}
    out["by_status"] = {k: int(v) for k, v in quests.groupby("status").size().items()}

    resolved = quests[quests["status"].isin(RESOLVED)].copy()
    resolved["success"] = resolved["status"].isin(SUCCESS).astype(int)
    rate = resolved.groupby("type")["success"].agg(["mean", "count"])
    out["success_rate"] = {TYPE_LABELS[k]: round(float(r["mean"]) * 100) for k, r in rate.iterrows()}
    overall = float(np.mean(resolved["success"])) * 100 if len(resolved) else 0.0
    out["overall_success"] = round(overall)

    # monthly activity, last 12 months, from XP events and quest creation
    start = (pd.Timestamp(today) - pd.DateOffset(months=11)).to_period("M")
    months = pd.period_range(start=start, periods=12, freq="M")
    ev_month = events.dropna(subset=["created_at"]).groupby(events["created_at"].dt.to_period("M")).size()
    q_month = quests.dropna(subset=["created_at"]).groupby(quests["created_at"].dt.to_period("M")).size()
    out["monthly"] = {
        "labels": [m.strftime("%b %y") for m in months],
        "actions": [int(ev_month.get(m, 0)) for m in months],
        "quests": [int(q_month.get(m, 0)) for m in months],
    }

    both = quests.dropna(subset=["registered_at", "submitted_at"])
    gaps = (both["submitted_at"] - both["registered_at"]).dt.total_seconds().to_numpy() / 86400
    gaps = gaps[gaps >= 0]
    out["avg_reg_to_sub"] = round(float(np.mean(gaps)), 1) if gaps.size else None
    out["median_reg_to_sub"] = round(float(np.median(gaps)), 1) if gaps.size else None

    days = xp_service.active_days(db, user_id)
    out["streak"] = xp_service.current_streak(days, today)
    out["longest_streak"] = xp_service.longest_streak(days)
    out["prize_won"] = float(quests.loc[quests["status"] == "won", "prize_amount"].sum())

    eligible = rate[rate["count"] >= 2].sort_values("mean", ascending=False)
    out["best_type"] = TYPE_LABELS[eligible.index[0]] if len(eligible) else None
    out["insights"] = _sentences(out, quests, events, today)
    return out


def _sentences(out, quests, events, today):
    lines = []
    if out["best_type"]:
        lines.append(f"You do best in {out['best_type']}s: {out['success_rate'][out['best_type']]}% of them "
                     f"ended in a final or a win. Prioritise more of these.")
    if out["avg_reg_to_sub"] is not None:
        lines.append(f"On average you submit {out['avg_reg_to_sub']} days after registering. "
                     + ("That is tight; start the back-plan the day you register."
                        if out["avg_reg_to_sub"] < 4 else "Nice pacing; keep using the back-planner."))
    if out["monthly"]["actions"] and max(out["monthly"]["actions"]) > 0:
        arr = np.array(out["monthly"]["actions"])
        best = int(arr.argmax())
        lines.append(f"Your busiest month was {out['monthly']['labels'][best]} with {int(arr[best])} actions, "
                     f"{round(arr[best] / max(arr.mean(), 1), 1)}x your monthly average.")
    upcoming = quests[(quests["deadline"] >= pd.Timestamp(today))
                      & (quests["deadline"] <= pd.Timestamp(today + timedelta(days=7)))
                      & (~quests["status"].isin(RESOLVED + ("submitted",)))]
    if len(upcoming):
        lines.append(f"{len(upcoming)} quest deadline{'s' if len(upcoming) != 1 else ''} land in the next 7 days. "
                     "Check the Clash Detector before taking on anything new.")
    if out["streak"] >= 2:
        lines.append(f"You are on a {out['streak']}-day streak. One small action today keeps the flame alive.")
    if not lines:
        lines.append("Add a few quests and finish a milestone to unlock personal insights.")
    while len(lines) < 3:
        lines.append("Every finished milestone earns XP and sharpens these insights.")
    return lines[:3]


def heatmap(db, user_id, today=None, weeks=53):
    """GitHub-style grid: list of weeks, each 7 cells {date, count, level 0-4}."""
    today = today or date.today()
    rows = db.execute("SELECT date(created_at) d, COUNT(*) c FROM xp_events WHERE user_id = ? "
                      "AND created_at >= date(?, '-371 day') GROUP BY d", (user_id, today.isoformat())).fetchall()
    counts = {r["d"]: r["c"] for r in rows}
    end = today + timedelta(days=(5 - today.weekday()) % 7 + 1)  # finish on Sunday
    start = end - timedelta(weeks=weeks) + timedelta(days=1)
    values = np.array([counts.get((start + timedelta(days=i)).isoformat(), 0) for i in range(weeks * 7)])
    q = np.percentile(values[values > 0], [25, 50, 75]) if (values > 0).any() else [1, 2, 3]
    grid, total = [], int(values.sum())
    for w in range(weeks):
        col = []
        for d in range(7):
            i = w * 7 + d
            day = start + timedelta(days=i)
            c = int(values[i])
            level = 0 if c == 0 else 1 + int(np.searchsorted(q, c, side="left"))
            col.append({"date": day.isoformat(), "count": c, "level": min(level, 4), "future": day > today})
        grid.append(col)
    months = []
    for w, col in enumerate(grid):
        first = date.fromisoformat(col[0]["date"])
        if first.day <= 7:
            months.append({"week": w, "label": first.strftime("%b")})
    return {"weeks": grid, "total": total, "months": months}


def chart_png(data, name):
    """Render a pixel-flavoured matplotlib PNG (fallback when Chart.js/CDN is unavailable). # CO4"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 3.4), dpi=90)
    fig.patch.set_facecolor("#0b0b2b")
    ax.set_facecolor("#0b0b2b")
    try:
        if name == "types":
            labels, vals = list(data["by_type"].keys()), list(data["by_type"].values())
            ax.bar(labels, vals, color=PALETTE[: len(vals)], edgecolor="#ffffff", linewidth=1.5)
            ax.set_title("Quests by type", color="#ffffff", family="monospace")
        elif name == "success":
            labels, vals = list(data["success_rate"].keys()), list(data["success_rate"].values())
            ax.barh(labels, vals, color="#3df58a", edgecolor="#ffffff", linewidth=1.5)
            ax.set_xlim(0, 100)
            ax.set_title("Success rate by type (%)", color="#ffffff", family="monospace")
        else:
            m = data["monthly"]
            x = np.arange(len(m["labels"]))
            ax.step(x, m["actions"], where="mid", color="#ff4fb4", linewidth=2.5, label="actions")
            ax.step(x, m["quests"], where="mid", color="#4fd8ff", linewidth=2.5, label="quests added")
            ax.set_xticks(x, m["labels"], rotation=45)
            ax.legend(facecolor="#0b0b2b", labelcolor="#ffffff")
            ax.set_title("Monthly activity", color="#ffffff", family="monospace")
        ax.tick_params(colors="#ffffff", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#ffffff")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        return buf.getvalue()
    finally:
        plt.close(fig)
