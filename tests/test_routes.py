"""Route tests with the Flask test client: every page, key flows, API auth, uploads."""
import io

import pytest

PAGES = ["/dashboard", "/map", "/quests/", "/quests/board", "/quests/new", "/quests/briefing", "/quests/import",
         "/quests/inventory", "/insights", "/insights.json", "/clashes", "/eligibility", "/notifications",
         "/notifications.json", "/party/", "/side-quests/", "/side-quests/new", "/training-log/",
         "/training-log/new", "/portfolio", "/badges", "/u/demo", "/settings", "/onboarding", "/calendar.ics",
         "/quests/export.csv", "/quests/export.json", "/portfolio/download.md", "/portfolio/download.txt",
         "/dashboard?q=hack&type=hackathon&status=open&sort=priority&range=month", "/quests/?sort=prize&mode=online"]


def first_quest(db, demo_id, title="Smart India Hackathon 2026%"):
    return db.execute("SELECT id FROM opportunities WHERE user_id = ? AND title LIKE ?", (demo_id, title)).fetchone()[0]


def test_public_pages(client):
    assert client.get("/").status_code == 200
    assert client.get("/login").status_code == 200
    assert client.get("/signup").status_code == 200
    assert client.get("/u/demo").status_code == 200
    assert client.get("/api/health").json["ok"] is True
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404 and b"GAME OVER" in resp.data


def test_login_required_redirects(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]


def test_bad_login(client):
    resp = client.post("/login", data={"username": "demo", "password": "nope"})
    assert b"Wrong username or password" in resp.data


@pytest.mark.parametrize("url", PAGES)
def test_every_page_renders(auth, url):
    resp = auth.get(url)
    assert resp.status_code == 200, url


def test_quest_pages_and_charts(auth, db, demo_id):
    qid = first_quest(db, demo_id)
    team = db.execute("SELECT id FROM teams").fetchone()[0]
    for url in (f"/quests/{qid}", f"/quests/{qid}/edit", f"/quests/{qid}/map", f"/quests/{qid}/calendar.ics",
                f"/party/{team}", "/insights/chart/types.png", "/insights/chart/success.png", "/insights/chart/monthly.png"):
        assert auth.get(url).status_code == 200, url
    assert auth.get("/insights/chart/types.png").data[:4] == b"\x89PNG"
    other = db.execute("SELECT id FROM opportunities WHERE user_id != ?", (demo_id,)).fetchone()[0]
    assert auth.get(f"/quests/{other}").status_code == 404  # can't peek at another player's quest


def test_signup_onboarding_and_empty_states(client):
    resp = client.post("/signup", data={"username": "newbie", "email": "n@example.com", "password": "password1",
                                        "confirm": "password1"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/onboarding")
    resp = client.post("/onboarding", data={"display_name": "Newbie", "avatar_look": "astro", "year": "2",
                                            "branch": "CSE", "college": "Test U", "skill__Python": "4"})
    assert resp.status_code == 302
    page = client.get("/dashboard").data
    assert b"No quests yet" in page and b"Load sample data" in page
    assert b"The road is empty" in client.get("/map").data
    resp = client.post("/load-sample", follow_redirects=True)
    assert b"Loaded" in resp.data


def test_signup_validation(client):
    resp = client.post("/signup", data={"username": "x", "email": "bad", "password": "1", "confirm": "2"})
    assert resp.status_code == 200
    for msg in (b"3-30 letters", b"valid email", b"at least 8", b"don&#39;t match"):
        assert msg in resp.data


def test_create_edit_delete_quest(auth, db, demo_id):
    resp = auth.post("/quests/new", data={"type": "competition", "title": "Test Cup", "deadline": "2026-12-01T18:00",
                                          "status": "interested", "mode": "online", "team_min": "1", "team_max": "3",
                                          "skills": "Python:3, Figma", "extra_domain": "coding", "auto_plan": "1",
                                          "auto_rounds": "1"})
    assert resp.status_code == 302
    qid = int(resp.headers["Location"].rsplit("/", 1)[1])
    row = db.execute("SELECT * FROM opportunities WHERE id = ?", (qid,)).fetchone()
    assert row["title"] == "Test Cup" and '"domain": "coding"' in row["extra_json"]
    assert db.execute("SELECT COUNT(*) FROM opportunity_skills WHERE opportunity_id = ?", (qid,)).fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM rounds WHERE opportunity_id = ?", (qid,)).fetchone()[0] == 4
    assert db.execute("SELECT COUNT(*) FROM milestones WHERE opportunity_id = ?", (qid,)).fetchone()[0] > 5
    resp = auth.post(f"/quests/{qid}/edit", data={"type": "competition", "title": "Test Cup 2", "deadline": "2026-12-02T18:00",
                                                 "status": "registered", "mode": "offline", "team_min": "1", "team_max": "3"})
    assert resp.status_code == 302
    row = db.execute("SELECT title, status, registered_at FROM opportunities WHERE id = ?", (qid,)).fetchone()
    assert row["title"] == "Test Cup 2" and row["status"] == "registered" and row["registered_at"]
    assert auth.post(f"/quests/{qid}/delete").status_code == 302
    assert db.execute("SELECT COUNT(*) FROM rounds WHERE opportunity_id = ?", (qid,)).fetchone()[0] == 0  # cascade


def test_quest_form_validation(auth):
    resp = auth.post("/quests/new", data={"type": "hackathon", "title": "", "deadline": "nope", "team_min": "4",
                                          "team_max": "2", "link": "ftp://x"})
    assert resp.status_code == 400
    for msg in (b"Title needs", b"valid deadline", b"Max team size", b"http"):
        assert msg in resp.data


def test_status_change_json_awards_xp(auth, db, demo_id):
    qid = first_quest(db, demo_id, "HackCBS%")
    before = db.execute("SELECT SUM(points) FROM xp_events WHERE user_id = ?", (demo_id,)).fetchone()[0]
    resp = auth.post(f"/quests/{qid}/status", json={"status": "submitted"}, headers={"X-Requested-With": "fetch"})
    assert resp.json["ok"] and resp.json["state"] == "done"
    assert any(p["kind"] == "xp" for p in resp.json["popups"])
    after = db.execute("SELECT SUM(points) FROM xp_events WHERE user_id = ?", (demo_id,)).fetchone()[0]
    assert after == before + 15 + 40  # register + submit
    again = auth.post(f"/quests/{qid}/status", json={"status": "submitted"}, headers={"X-Requested-With": "fetch"})
    assert again.json["popups"] == []
    bad = auth.post(f"/quests/{qid}/status", json={"status": "flying"}, headers={"X-Requested-With": "fetch"})
    assert bad.status_code == 400


def test_milestone_toggle_and_trophy(auth, db, demo_id):
    qid = first_quest(db, demo_id, "ETHIndia%")
    auth.post(f"/quests/{qid}/plan")
    phase = db.execute("SELECT id FROM milestones WHERE opportunity_id = ? AND parent_id IS NULL ORDER BY seq", (qid,)).fetchone()[0]
    resp = auth.post(f"/quests/milestones/{phase}/toggle", headers={"X-Requested-With": "fetch"})
    assert resp.json["done"] == 1 and resp.json["progress"] > 0
    kids = db.execute("SELECT MIN(done) FROM milestones WHERE parent_id = ?", (phase,)).fetchone()[0]
    assert kids == 1  # recursive CTE ticked every child
    assert auth.post(f"/quests/{qid}/claim-trophy").status_code == 400  # road not finished yet
    db.execute("UPDATE milestones SET done = 1 WHERE opportunity_id = ?", (qid,))
    db.execute("UPDATE rounds SET status = 'cleared' WHERE opportunity_id = ?", (qid,))
    db.commit()
    resp = auth.post(f"/quests/{qid}/claim-trophy")
    assert resp.json["ok"] and resp.json["first"]
    assert any("Trophy Hunter" in p["text"] or p["kind"] == "xp" for p in resp.json["popups"])


def test_rounds_crud(auth, db, demo_id):
    qid = first_quest(db, demo_id, "HackCBS%")
    auth.post(f"/quests/{qid}/rounds", data={"name": "Demo Day", "deadline": "2026-12-20T10:00"})
    rid = db.execute("SELECT id FROM rounds WHERE opportunity_id = ? AND name = 'Demo Day'", (qid,)).fetchone()[0]
    resp = auth.post(f"/quests/rounds/{rid}/update", json={"status": "cleared"}, headers={"X-Requested-With": "fetch"})
    assert resp.json["ok"]
    assert db.execute("SELECT status FROM rounds WHERE id = ?", (rid,)).fetchone()[0] == "cleared"
    auth.post(f"/quests/rounds/{rid}/delete")
    assert db.execute("SELECT COUNT(*) FROM rounds WHERE id = ?", (rid,)).fetchone()[0] == 0


def test_briefing_parse_and_save(auth, db, demo_id):
    text = "HackOverflow 3.0 hackathon. Teams of 2-4. Prize ₹50,000. Register by 15 Nov 2026: https://x.example.com"
    resp = auth.post("/quests/briefing", data={"text": text})
    assert resp.status_code == 200 and b"confidence" in resp.data and b"HackOverflow 3.0 hackathon" in resp.data
    resp = auth.post("/quests/briefing/save", data={"title": "HackOverflow 3.0", "type": "hackathon",
                                                    "deadline": "2026-11-15T23:59", "status": "interested", "mode": "online",
                                                    "team_min": "2", "team_max": "4", "round_name": ["Finals"],
                                                    "round_deadline": ["2026-11-30T10:00"]})
    assert resp.status_code == 302
    row = db.execute("SELECT id, source FROM opportunities WHERE title = 'HackOverflow 3.0'").fetchone()
    assert row["source"] == "briefing"
    assert db.execute("SELECT name FROM rounds WHERE opportunity_id = ?", (row["id"],)).fetchone()[0] == "Finals"


def test_import_upload_with_bad_rows(auth):
    data = "title,type,deadline\nGood,workshop,2026-12-01\nBad,party,never\n"
    resp = auth.post("/quests/import", data={"file": (io.BytesIO(data.encode()), "q.csv")},
                     content_type="multipart/form-data")
    assert resp.status_code == 200 and b"Validation report" in resp.data and b"Imported 1 of 2" in resp.data


def test_asset_upload_rules(auth, db, demo_id, app):
    qid = first_quest(db, demo_id)
    resp = auth.post(f"/quests/{qid}/assets", data={"label": "evil", "file": (io.BytesIO(b"x"), "run.exe")},
                     content_type="multipart/form-data", follow_redirects=True)
    assert b"allowed. Use PDF" in resp.data  # flash text arrives JSON-encoded for the toast
    resp = auth.post(f"/quests/{qid}/assets", data={"label": "Deck", "category": "ppt",
                                                    "file": (io.BytesIO(b"%PDF-1.4 test"), "../../deck.pdf")},
                     content_type="multipart/form-data")
    assert resp.status_code == 302
    asset = db.execute("SELECT * FROM assets WHERE label = 'Deck'").fetchone()
    assert ".." not in asset["stored_name"] and asset["original_name"] == "deck.pdf"
    assert auth.get(f"/quests/assets/{asset['id']}/file").data.startswith(b"%PDF")
    big = auth.post(f"/quests/{qid}/assets", data={"file": (io.BytesIO(b"0" * (5 * 1024 * 1024 + 10)), "big.pdf")},
                    content_type="multipart/form-data")
    assert big.status_code == 413
    auth.post(f"/quests/assets/{asset['id']}/delete")
    assert db.execute("SELECT COUNT(*) FROM assets WHERE id = ?", (asset["id"],)).fetchone()[0] == 0


def test_party_flow(auth, client, db):
    resp = auth.post("/party/new", data={"name": "Test Party"})
    tid = int(resp.headers["Location"].rsplit("/", 1)[1])
    auth.post(f"/party/{tid}/invite", data={"username": "kabir"})
    assert db.execute("SELECT status FROM team_members WHERE team_id = ? AND user_id = (SELECT id FROM users WHERE username='kabir')",
                      (tid,)).fetchone()[0] == "invited"
    auth.post(f"/party/{tid}/tasks", data={"title": "Build it"})
    task = db.execute("SELECT id FROM tasks WHERE team_id = ?", (tid,)).fetchone()[0]
    assert auth.post(f"/party/tasks/{task}/move", json={"status": "done"}, headers={"X-Requested-With": "fetch"}).json["ok"]
    assert db.execute("SELECT COUNT(*) FROM team_log WHERE team_id = ?", (tid,)).fetchone()[0] >= 3
    auth.post(f"/party/{tid}/leave")
    assert db.execute("SELECT COUNT(*) FROM teams WHERE id = ?", (tid,)).fetchone()[0] == 0


def test_feed_vote_and_adopt(auth, db):
    post = db.execute("SELECT id, title FROM feed_posts LIMIT 1").fetchone()
    first = auth.post(f"/side-quests/{post['id']}/vote", headers={"X-Requested-With": "fetch"}).json
    second = auth.post(f"/side-quests/{post['id']}/vote", headers={"X-Requested-With": "fetch"}).json
    assert first["voted"] != second["voted"]
    assert auth.post(f"/side-quests/{post['id']}/adopt").status_code == 302
    assert db.execute("SELECT source FROM opportunities WHERE title = ? AND source = 'side-quest'", (post["title"],)).fetchone()


def test_journal_search_and_tags(auth):
    auth.post("/training-log/new", data={"title": "Unique lesson zebra", "lessons": "Practise pitching", "rating": "4",
                                         "tags": "pitch, Zebra"})
    assert b"Unique lesson zebra" in auth.get("/training-log/?q=zebra").data
    assert b"Unique lesson zebra" in auth.get("/training-log/?tag=zebra").data
    assert b"Unique lesson zebra" not in auth.get("/training-log/?q=nothing-matches").data


def test_api_token_auth(client, db):
    token = db.execute("SELECT api_token FROM users WHERE username = 'demo'").fetchone()[0]
    assert client.get("/api/opportunities").status_code == 401
    assert client.get("/api/opportunities", headers={"Authorization": "Bearer wrong"}).status_code == 401
    data = client.get("/api/opportunities?upcoming=1&limit=5", headers={"Authorization": f"Bearer {token}"}).json
    assert data["count"] == 5 and all(o["deadline"] for o in data["opportunities"])
    stats = client.get(f"/api/stats?token={token}").json
    assert stats["player"] == "Riya Kapoor" and stats["xp"]["level"] >= 1


def test_privacy_toggle(auth, client):
    auth.post("/u/demo/privacy")
    client.post("/logout")
    assert client.get("/u/demo").status_code == 403


def test_csrf_is_enforced(seeded_db, tmp_path):
    import shutil
    from app import create_app
    path = str(tmp_path / "csrf.db")
    shutil.copy(seeded_db, path)
    app = create_app({"TESTING": True, "DATABASE": path, "START_SCHEDULER": False})
    resp = app.test_client().post("/login", data={"username": "demo", "password": "demo1234"})
    assert resp.status_code == 400
