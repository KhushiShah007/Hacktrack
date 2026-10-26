"""Import/export (CO2) and the Quest Map layout generator."""
import csv
import io
import json

import pytest

from app.models import Opportunity
from app.services import ics, io_utils, questmap


# ---------------- import / export ----------------
def test_csv_round_trip(db, demo_id):
    opps = Opportunity.for_user(db, demo_id)
    text = io_utils.to_csv(opps)
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == len(opps) and rows[0]["title"]
    report = io_utils.import_records(db, demo_id, rows)
    assert report["created"] == len(opps) and report["errors"] == []


def test_json_export_shape(db, demo_id):
    data = json.loads(io_utils.to_json(Opportunity.for_user(db, demo_id)))
    assert data["version"] == 1 and isinstance(data["quests"], list)


def test_import_validation_report(db, demo_id):
    records = [
        {"title": "Good one", "type": "hackathon", "deadline": "2026-12-01 10:00"},
        {"title": "x", "type": "party", "deadline": "soon"},
        {"title": "Bad numbers", "type": "workshop", "deadline": "2026-12-01", "prize_amount": "lots", "team_min": "3", "team_max": "1"},
        "not a dict",
    ]
    report = io_utils.import_records(db, demo_id, records)
    assert report["created"] == 1 and report["total"] == 4
    rows = {row: msgs for row, msgs in report["errors"]}
    assert any("title" in m for m in rows[3]) and any("type" in m for m in rows[3]) and any("deadline" in m for m in rows[3])
    assert any("prize_amount" in m for m in rows[4])
    assert rows[5] == ["record is not an object"]


@pytest.mark.parametrize("name,data,message", [
    ("q.json", b"{not json", "JSON is invalid"),
    ("q.csv", b"name,when\nA,B", "header row"),
    ("q.txt", b"hello", "Only .csv and .json"),
    ("q.csv", b"\xff\xfe\x00bad", "UTF-8"),
])
def test_parse_upload_errors(name, data, message):
    with pytest.raises(ValueError, match=message):
        io_utils.parse_upload(name, data)


def test_parse_upload_json_variants():
    assert io_utils.parse_upload("a.json", b'[{"title": "x"}]') == [{"title": "x"}]
    assert io_utils.parse_upload("a.json", b'{"quests": [{"title": "y"}]}') == [{"title": "y"}]


def test_ics_has_events_and_escaping():
    body = ics.build_ics([{"uid": "a", "title": "Hack, Day; 1", "when": "2026-11-01 10:00", "description": "line1\nline2"}])
    assert body.startswith("BEGIN:VCALENDAR") and body.strip().endswith("END:VCALENDAR")
    assert "SUMMARY:Hack\\, Day\\; 1" in body and "DTSTART:20261101T100000" in body and "\r\n" in body


# ---------------- quest map layout ----------------
def pins(n, states=None):
    return [{"title": f"Q{i}", "state": (states or {}).get(i, "pending")} for i in range(n)]


@pytest.mark.parametrize("n", [1, 2, 5, 12, 30])
def test_layout_scales_with_pin_count(n):
    layout = questmap.build_layout(pins(n), seed=3)
    assert len(layout["pins"]) == n
    assert len(layout["segments"]) == n + 1  # start -> pins -> trophy
    ys = [p["y"] for p in layout["pins"]]
    assert ys == sorted(ys, reverse=True)  # first pin at the bottom, road climbs
    assert layout["trophy"]["y"] < min(ys) and layout["start"]["y"] > max(ys)
    sides = [p["side"] for p in layout["pins"]]
    assert all(a != b for a, b in zip(sides, sides[1:]))  # signboards alternate
    for p in layout["pins"]:
        s = p["sign"]
        assert 0 <= s["x"] and s["x"] + s["w"] <= layout["width"]


def test_scenery_is_seeded_and_avoids_signs():
    a = questmap.build_layout(pins(6), seed=11)
    b = questmap.build_layout(pins(6), seed=11)
    c = questmap.build_layout(pins(6), seed=12)
    assert a["scenery"] == b["scenery"] and a["scenery"] != c["scenery"]
    for item in a["scenery"]:
        for p in a["pins"]:
            s = p["sign"]
            inside = s["x"] < item["x"] < s["x"] + s["w"] and s["y"] < item["y"] < s["y"] + s["h"]
            assert not inside


def test_empty_map_and_avatar_index():
    layout = questmap.build_layout([], seed=1)
    assert layout["pins"] == [] and len(layout["segments"]) == 1
    assert questmap.avatar_index(pins(4, {0: "done", 1: "won"})) == 2
    assert questmap.avatar_index(pins(3, {0: "done", 1: "missed", 2: "done"})) == 3
    assert questmap.avatar_index(pins(3, {1: "done"})) == 0
