"""Password recovery, self profile update and branded e-mail templates."""
from __future__ import annotations

from app.services import email_templates, platform_settings as platform_cfg


def _create_user(client, auth_headers, **overrides):
    payload = {
        "username": "resetuser",
        "password": "Passw0rd!",
        "email": "resetuser@example.com",
        "full_name": "Reset User",
        "role": "operator",
    }
    payload.update(overrides)
    r = client.post("/api/v1/auth/users", json=payload, headers=auth_headers)
    assert r.status_code in (201, 409), r.text
    return payload


def test_profile_self_update(client):
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"},
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    r = client.patch(
        "/api/v1/auth/profile",
        json={"full_name": "Ops Lead", "email": "ops-admin@example.com"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "ops-admin@example.com"
    assert body["full_name"] == "Ops Lead"

    # Cleanup so we do not leak an e-mail onto admin for other tests.
    client.patch("/api/v1/auth/profile", json={"email": None}, headers=headers)


def test_profile_locale_timezone(client):
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"},
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    r = client.patch(
        "/api/v1/auth/profile",
        json={"locale": "en", "timezone": "America/New_York"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["locale"] == "en"
    assert body["timezone"] == "America/New_York"

    bad = client.patch(
        "/api/v1/auth/profile",
        json={"locale": "fr"},
        headers=headers,
    )
    assert bad.status_code == 422

    client.patch(
        "/api/v1/auth/profile",
        json={"locale": "zh", "timezone": "Asia/Shanghai"},
        headers=headers,
    )


def test_forgot_password_is_generic_for_unknown_user(client):
    r = client.post(
        "/api/v1/auth/forgot-password",
        json={"identifier": "does-not-exist"},
    )
    assert r.status_code == 200
    assert r.json()["sent"] is True


def test_forgot_and_reset_password_flow(client, auth_headers, monkeypatch):
    _create_user(client, auth_headers, username="resetflow", email="resetflow@example.com")

    monkeypatch.setattr("app.api.v1.auth.secrets.randbelow", lambda n: 123456)

    sent: dict = {}

    def _capture(db, *, to, code, ttl_minutes=15):
        sent["to"] = to
        sent["code"] = code
        return True, "sent"

    monkeypatch.setattr("app.api.v1.auth.email_svc.send_password_reset_email", _capture)

    r = client.post(
        "/api/v1/auth/forgot-password",
        json={"identifier": "resetflow@example.com"},
    )
    assert r.status_code == 200
    assert sent["code"] == "123456"
    assert sent["to"] == "resetflow@example.com"

    # Wrong code rejected.
    bad = client.post(
        "/api/v1/auth/reset-password",
        json={"identifier": "resetflow", "code": "000000", "new_password": "BrandNew1!"},
    )
    assert bad.status_code == 400

    ok = client.post(
        "/api/v1/auth/reset-password",
        json={"identifier": "resetflow", "code": "123456", "new_password": "BrandNew1!"},
    )
    assert ok.status_code == 204

    # Old password no longer works, new one does.
    old = client.post(
        "/api/v1/auth/login",
        data={"username": "resetflow", "password": "Passw0rd!"},
    )
    assert old.status_code == 401
    new = client.post(
        "/api/v1/auth/login",
        data={"username": "resetflow", "password": "BrandNew1!"},
    )
    assert new.status_code == 200
    assert new.json().get("access_token")

    # Code cannot be reused.
    reuse = client.post(
        "/api/v1/auth/reset-password",
        json={"identifier": "resetflow", "code": "123456", "new_password": "Another1!"},
    )
    assert reuse.status_code == 400


def test_login_security_exposes_reset_flag(client):
    r = client.get("/api/v1/auth/login-security")
    assert r.status_code == 200
    assert "password_reset_enabled" in r.json()


def test_branded_email_renders_code_and_brand(client):
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        plat = platform_cfg.get_or_create(db)
        html = email_templates.render_email(
            plat,
            heading="登录验证码",
            intro="测试邮件",
            code="246810",
            code_caption="登录验证码",
        )
    finally:
        db.close()
    assert "246810" in html
    assert plat.product_name in html
    assert "<!DOCTYPE html>" in html
    # White text sits on colored areas (header + code chip); those MUST carry a
    # solid background-color fallback so the code stays visible even when an
    # e-mail client strips CSS gradients (otherwise it renders white-on-white).
    assert "background-color:#0f172a" in html  # header fallback
    assert html.count("background-color:") >= 3  # header + divider + code chip
