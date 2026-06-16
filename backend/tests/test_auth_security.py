"""Auth security: rate limit, MFA, SSE tickets."""
from __future__ import annotations

import pyotp

from app.models.enums import MfaMethod
from app.models.user import User
from app.services import auth_security


def test_login_rate_limit(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.auth.auth_security.is_ip_rate_limited",
        lambda db, plat, ip_address: True,
    )
    r = client.post(
        "/api/v1/auth/login/json",
        json={"username": "admin", "password": "admin123"},
    )
    assert r.status_code == 429


def test_totp_setup_and_login(client, auth_headers):
    secret = auth_security.new_totp_secret()
    code = pyotp.TOTP(secret).now()

    user = client.get("/api/v1/auth/me", headers=auth_headers).json()
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        row = db.get(User, user["id"])
        row.totp_secret_encrypted = auth_security.encrypt_secret(secret)
        row.mfa_enabled = True
        row.mfa_method = MfaMethod.TOTP
        db.commit()
    finally:
        db.close()

    step1 = client.post(
        "/api/v1/auth/login/json",
        json={"username": user["username"], "password": "admin123"},
    ).json()
    assert step1.get("mfa_required") is True
    assert step1.get("mfa_token")

    step2 = client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": step1["mfa_token"], "code": code, "method": "totp"},
    )
    assert step2.status_code == 200
    assert step2.json().get("access_token")


def test_sse_ticket_no_jwt_in_url(client, auth_headers):
    ticket = client.post("/api/v1/auth/stream/ticket", headers=auth_headers).json()
    assert ticket.get("ticket")
    assert "eyJ" not in ticket["ticket"]
    missing = client.get("/api/v1/stream/events")
    assert missing.status_code == 422


def test_stream_rejects_raw_jwt(client, auth_headers):
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"},
    ).json()
    token = login["access_token"]
    r = client.get(f"/api/v1/stream/events?token={token}")
    assert r.status_code == 422
