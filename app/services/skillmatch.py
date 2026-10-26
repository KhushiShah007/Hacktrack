"""Team Skill-Match: weighted Jaccard + proficiency coverage for a player and for a party."""
from functools import reduce


def _norm_required(required):
    """{'Python': 3} importance 1-3 -> weight 0-1"""
    return {k.lower(): (v or 2) / 3 for k, v in required.items()}


def _norm_user(skills):
    """{'Python': 4} proficiency 1-5 -> weight 0-1"""
    return {k.lower(): (v or 3) / 5 for k, v in skills.items()}


def weighted_jaccard(a, b):
    """sum(min) / sum(max) over the union of keys. # CO1 lambda/map/reduce"""
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    mins = sum(map(lambda k: min(a.get(k, 0), b.get(k, 0)), keys))
    maxs = sum(map(lambda k: max(a.get(k, 0), b.get(k, 0)), keys))
    return mins / maxs if maxs else 0.0


def coverage(req, have):
    """How much of the importance-weighted requirement the skills cover."""
    total = sum(req.values())
    if not total:
        return 0.0
    return sum(w * min(1.0, have.get(k, 0) / 0.8) for k, w in req.items()) / total


def fit_score(required, user_skills):
    """Return {'score': 0-100, 'jaccard', 'coverage', 'gaps', 'matched'} for one player. # CO1"""
    req = _norm_required(required)
    have = _norm_user(user_skills)
    if not req:
        return {"score": 60, "jaccard": 0, "coverage": 0, "gaps": [], "matched": [], "note": "No skills listed for this quest."}
    jac = weighted_jaccard(req, {k: v for k, v in have.items() if k in req} or {"__none__": 0})
    cov = coverage(req, have)
    names = {k.lower(): k for k in required}
    gaps = [names[k] for k in req if have.get(k, 0) < 0.4]
    matched = [names[k] for k in req if have.get(k, 0) >= 0.4]
    score = round(100 * (0.5 * jac + 0.5 * cov))
    return {"score": score, "jaccard": round(jac, 2), "coverage": round(cov, 2), "gaps": gaps, "matched": matched}


def team_fit(required, members):
    """members: {name: {skill: proficiency}}. Team vector = best member per skill. # CO1 reduce"""
    req = _norm_required(required)
    normed = {name: _norm_user(sk) for name, sk in members.items()}
    team_vec = reduce(
        lambda acc, vec: {k: max(acc.get(k, 0), vec.get(k, 0)) for k in set(acc) | set(vec)},
        normed.values(), {})
    names = {k.lower(): k for k in required}
    assignments = []
    for key in req:
        holders = sorted(normed.items(), key=lambda kv: kv[1].get(key, 0), reverse=True)
        best_name, best_vec = holders[0] if holders else (None, {})
        level = best_vec.get(key, 0)
        assignments.append({
            "skill": names[key],
            "member": best_name if level >= 0.4 else None,
            "level": round(level * 5),
        })
    team_score = fit_score(required, {k: v * 5 for k, v in team_vec.items()})
    per_member = {name: fit_score(required, sk)["score"] for name, sk in members.items()}
    return {
        "score": team_score["score"],
        "gaps": team_score["gaps"],
        "assignments": assignments,
        "per_member": per_member,
    }
