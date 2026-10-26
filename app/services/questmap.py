"""Quest Map layout generator: road path, pins, signboards and seeded scenery for any pin count."""
import random

SCENERY_KINDS = ["tree", "tree", "pine2", "sunflower", "mushroom", "log", "bush", "flowers"]
CRITTERS = ["cat", "raccoon"]


def _bezier(p0, p1, p2, p3, steps=24):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def _segment(a, b):
    """Cubic with vertical tangents at both ends, so the road runs straight up past each pin."""
    mid = (a[1] + b[1]) / 2
    return (a, (a[0], mid), (b[0], mid), b)


def _rects_overlap(r1, r2, pad=0):
    return not (r1[0] + r1[2] + pad < r2[0] or r2[0] + r2[2] + pad < r1[0]
                or r1[1] + r1[3] + pad < r2[1] or r2[1] + r2[3] + pad < r1[1])


def build_layout(pins, seed=7, width=400, gap=165, top=210, bottom=200, sign_w=0.54, sign_h=86):
    """Lay out `pins` (bottom = first) along a winding road. Returns a JSON-able dict. # CO1"""
    n = len(pins)
    height = top + max(n - 1, 0) * gap + bottom + 60
    left_x, right_x = width * 0.30, width * 0.70
    start = (width * 0.30, height - 70)
    waypoints = []
    out_pins = []
    for i, pin in enumerate(pins):
        x = right_x if i % 2 == 0 else left_x
        y = height - bottom - i * gap
        waypoints.append((x, y))
        sw = width * sign_w
        sx = width * 0.035 if x > width / 2 else width - sw - width * 0.035
        sign = {"x": round(sx, 1), "y": round(y - sign_h / 2 - 6, 1), "w": round(sw, 1), "h": sign_h}
        out_pins.append({**pin, "index": i, "x": round(x, 1), "y": round(y, 1),
                         "side": "left" if x > width / 2 else "right", "sign": sign})
    trophy_x = right_x  # trophy always top-right, the map title owns the top-left
    trophy = (trophy_x if n else width * 0.5, top - 110 if n else height - 260)
    chain = [start, *waypoints, trophy]

    segments, polyline = [], []
    for a, b in zip(chain, chain[1:]):
        p0, p1, p2, p3 = _segment(a, b)
        segments.append(f"M{p0[0]:.1f},{p0[1]:.1f} C{p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f} {p3[0]:.1f},{p3[1]:.1f}")
        polyline += _bezier(p0, p1, p2, p3)
    path_d = (f"M{start[0]:.1f},{start[1]:.1f} "
              + " ".join(s.split(" ", 1)[1] for s in segments))

    # seeded scenery that avoids the road, signboards, pins and the HUD corners
    rng = random.Random(seed)
    blocked = [(p["sign"]["x"], p["sign"]["y"], p["sign"]["w"], p["sign"]["h"]) for p in out_pins]
    blocked += [(p["x"] - 22, p["y"] - 60, 44, 64) for p in out_pins]
    blocked += [(trophy[0] - 50, trophy[1] - 60, 100, 110), (0, height - 120, 150, 70), (0, 0, width, 150)]
    scenery = []
    want = 6 + n * 2
    attempts = 0
    while len(scenery) < want and attempts < want * 40:
        attempts += 1
        kind = rng.choice(SCENERY_KINDS)
        w, h = (40, 56) if kind in ("tree", "pine2") else (30, 34)
        x = rng.uniform(4, width - w - 4)
        y = rng.uniform(150, height - 110)
        box = (x, y, w, h)
        if any(_rects_overlap(box, b, pad=4) for b in blocked):
            continue
        if any(abs(px - (x + w / 2)) < 40 and abs(py - (y + h / 2)) < 40 for px, py in polyline):
            continue
        blocked.append(box)
        scenery.append({"kind": kind, "x": round(x, 1), "y": round(y, 1), "flip": rng.random() < 0.5})
    # critters walk the brick strip: raccoon mid-left, cat on the right, never on START
    critter_x = {"raccoon": rng.uniform(width * 0.40, width * 0.55), "cat": rng.uniform(width * 0.68, width * 0.84)}
    critters = [{"kind": c, "x": round(critter_x[c], 1), "flip": rng.random() < 0.5} for c in CRITTERS]

    return {
        "width": width, "height": round(height), "path": path_d, "segments": segments,
        "pins": out_pins, "start": {"x": start[0], "y": start[1]},
        "trophy": {"x": round(trophy[0], 1), "y": round(trophy[1], 1)},
        "scenery": scenery, "critters": critters,
    }


def avatar_index(pins):
    """The avatar stands at the first pin that is not finished (len(pins) = at the trophy)."""
    for i, p in enumerate(pins):
        if p.get("state") not in ("done", "won", "missed"):
            return i
    return len(pins)
