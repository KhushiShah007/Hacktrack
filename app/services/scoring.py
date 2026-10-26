"""Priority Score: a transparent weighted formula with a per-factor breakdown."""
import math

from ..utils import days_left

WEIGHTS = {"urgency": 0.35, "value": 0.15, "fit": 0.20, "effort": 0.10, "status": 0.20}
STATUS_WEIGHT = {
    "interested": 0.6, "preparing": 0.9, "registered": 1.0, "submitted": 0.15,
    "shortlisted": 0.85, "won": 0.0, "rejected": 0.0,
}


def urgency_factor(d):
    if d is None or d < 0:
        return 0.0
    return math.exp(-d / 7)  # 1.0 now, ~0.37 in a week, ~0.01 in a month


def value_factor(prize_amount):
    # log scale: Rs 1k ~ 0.5, Rs 1 lakh ~ 0.83, Rs 10 lakh+ = 1
    return min(1.0, math.log10(prize_amount + 1) / 6) if prize_amount > 0 else 0.15


def effort_factor(hours):
    return 1 - min(hours, 80) / 80 * 0.8  # quick wins score higher, big quests never drop to 0


def priority_score(opp, fit=60, ref=None):
    """Return (score 0-100, breakdown). `fit` is the 0-100 skill-fit score. # CO1"""
    d = days_left(opp.deadline, ref)
    factors = {
        "urgency": urgency_factor(d),
        "value": value_factor(opp.prize_amount),
        "fit": max(0, min(fit, 100)) / 100,
        "effort": effort_factor(opp.effort_estimate()),
        "status": STATUS_WEIGHT.get(opp.status, 0.5),
    }
    if d is not None and d < 0:
        factors["status"] = 0.0
    breakdown = {k: {"factor": round(v, 2), "weight": WEIGHTS[k], "points": round(100 * v * WEIGHTS[k], 1)}
                 for k, v in factors.items()}
    score = round(sum(b["points"] for b in breakdown.values()))
    return score, breakdown


def top_n(opps, fits, n=5, ref=None):
    """'Do this first': open quests with a future deadline, ranked by score. # CO1 lambda/filter"""
    active = filter(lambda o: o.status not in ("won", "rejected", "submitted")
                    and (days_left(o.deadline, ref) or -1) >= 0, opps)
    scored = map(lambda o: (o, *priority_score(o, fits.get(o.id, 60), ref)), active)
    return sorted(scored, key=lambda t: t[1], reverse=True)[:n]


def breakdown_text(breakdown):
    return " | ".join(f"{k}: {v['factor']:.2f} x {v['weight']:.2f} = {v['points']}" for k, v in breakdown.items())
