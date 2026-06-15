"""Pytest fixtures: isolated DB + authenticated test client."""
from __future__ import annotations

import os
import tempfile

import pytest

# Configure an isolated SQLite DB BEFORE importing the app/settings.
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["BUGIS_DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["BUGIS_DRY_RUN"] = "true"
os.environ["BUGIS_SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402

from app.bootstrap import ensure_bugis_controller, ensure_superuser  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    init_db()
    db = SessionLocal()
    try:
        ensure_superuser(db)
        ensure_bugis_controller(db)
    finally:
        db.close()
    yield
    os.close(_db_fd)
    os.unlink(_db_path)


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def auth_headers(client):
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
