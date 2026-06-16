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
os.environ["BUGIS_SKIP_MIGRATE"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app.bootstrap import ensure_bugis_controller, ensure_cluster_node, ensure_superuser  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    init_db()
    db = SessionLocal()
    try:
        ensure_superuser(db)
        ensure_bugis_controller(db)
        ensure_cluster_node(db)
    finally:
        db.close()
    yield
    os.close(_db_fd)
    os.unlink(_db_path)


@pytest.fixture(autouse=True)
def _reset_dry_run():
    """Keep tests isolated when a case toggles platform dry-run off."""
    from app.core.config import settings

    settings.dry_run = True
    yield
    settings.dry_run = True


@pytest.fixture(autouse=True)
def _unlock_admin():
    """Reset admin lockout / MFA between tests (shared SQLite DB)."""
    from app.models.enums import MfaMethod
    from app.models.user import User

    db = SessionLocal()
    try:
        for user in db.query(User).filter(User.username == "admin").all():
            user.failed_login_attempts = 0
            user.locked_until = None
            user.mfa_enabled = False
            user.mfa_method = MfaMethod.NONE
            user.totp_secret_encrypted = None
        db.commit()
    finally:
        db.close()
    yield


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
    body = resp.json()
    token = body.get("access_token")
    assert token, body
    return {"Authorization": f"Bearer {token}"}
