"""Platform branding settings API tests."""
from __future__ import annotations


def test_public_branding_no_auth(client):
    r = client.get("/api/v1/system/branding")
    assert r.status_code == 200
    body = r.json()
    assert body["product_name"] == "Bugis Network"
    assert "header_title" in body
    assert body["accent_color"] == "#52c41a"


def test_update_branding(client, auth_headers):
    r = client.patch(
        "/api/v1/settings/platform",
        headers=auth_headers,
        json={
            "product_name": "Acme Fabric",
            "header_title": "Acme DCI Ops",
            "login_title": "Acme Login",
        },
    )
    assert r.status_code == 200
    assert r.json()["product_name"] == "Acme Fabric"

    pub = client.get("/api/v1/system/branding").json()
    assert pub["product_name"] == "Acme Fabric"
    assert pub["login_title"] == "Acme Login"


def test_branding_requires_auth_to_update(client):
    r = client.patch(
        "/api/v1/settings/platform",
        json={"product_name": "Hacker"},
    )
    assert r.status_code == 401
