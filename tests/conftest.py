import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.db import connect  # noqa: E402

REF = datetime(2026, 10, 26, 12, 0)


@pytest.fixture(scope="session")
def seeded_db(tmp_path_factory):
    """One fully seeded database, copied for each test that writes to it."""
    import seed
    path = str(tmp_path_factory.mktemp("db") / "seeded.db")
    seed.seed(path)
    return path


@pytest.fixture
def app(seeded_db, tmp_path):
    import shutil
    db_path = str(tmp_path / "test.db")
    shutil.copy(seeded_db, db_path)
    app = create_app({
        "TESTING": True,
        "DATABASE": db_path,
        "WTF_CSRF_ENABLED": False,
        "START_SCHEDULER": False,
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
    })
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth(client):
    resp = client.post("/login", data={"username": "demo", "password": "demo1234"})
    assert resp.status_code == 302
    return client


@pytest.fixture
def db(app):
    conn = connect(app.config["DATABASE"])
    yield conn
    conn.close()


@pytest.fixture
def demo_id(db):
    return db.execute("SELECT id FROM users WHERE username = 'demo'").fetchone()[0]
