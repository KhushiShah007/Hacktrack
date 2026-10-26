"""Eligibility Checker: compares the player's year/branch/college with a quest's rules."""
from ..utils import csv_list

ELIGIBLE, NOT_ELIGIBLE, CHECK = "Eligible", "Not eligible", "Check manually"


def check(user, opp):
    """user: object/dict with year, branch, college. Returns (verdict, reason). # CO1"""
    get = (lambda k: user.get(k)) if isinstance(user, dict) else (lambda k: getattr(user, k, None))
    years = [int(y) for y in csv_list(opp.eligible_years) if y.isdigit()]
    branches = [b.lower() for b in csv_list(opp.eligible_branches)]
    colleges = [c.lower() for c in csv_list(opp.eligible_colleges)]
    has_rules = bool(years or branches or colleges)

    if not has_rules:
        if opp.eligibility_text.strip():
            return CHECK, f"Rules are free text only: \"{opp.eligibility_text[:80]}\""
        return ELIGIBLE, "No restrictions listed."

    missing = []
    if years and not get("year"):
        missing.append("year")
    if branches and not get("branch"):
        missing.append("branch")
    if colleges and not get("college"):
        missing.append("college")
    if missing:
        return CHECK, f"Add your {', '.join(missing)} in Settings so we can check."

    reasons = []
    if years and int(get("year")) not in years:
        reasons.append(f"open to year {', '.join(map(str, years))}; you are in year {get('year')}")
    if branches and str(get("branch")).lower() not in branches:
        reasons.append(f"branches {', '.join(b.upper() for b in branches)} only; you are {get('branch')}")
    if colleges and not any(c in str(get("college")).lower() for c in colleges):
        reasons.append(f"restricted to {', '.join(csv_list(opp.eligible_colleges))}")
    if reasons:
        return NOT_ELIGIBLE, "; ".join(reasons).capitalize() + "."
    return ELIGIBLE, "Your year, branch and college match the rules."
