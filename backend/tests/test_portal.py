"""Tenant portal access control tests."""
from __future__ import annotations

import itertools

_seq = itertools.count(1)


def _platform_admin(client, auth_headers):
    return client.get("/api/v1/auth/me", headers=auth_headers).json()


def test_create_tenant_portal_user_and_login(client, auth_headers):
    n = next(_seq)
    tenant = client.post(
        "/api/v1/tenants",
        headers=auth_headers,
        json={"name": f"Portal Co {n}", "code": f"PC{n}", "type": "enterprise"},
    ).json()
    user = client.post(
        f"/api/v1/tenants/{tenant['id']}/users",
        headers=auth_headers,
        json={
            "username": f"portal{n}",
            "password": "PortalPass123",
            "full_name": "Portal User",
            "role": "tenant_viewer",
        },
    ).json()
    assert user["scope"] == "tenant"
    assert user["tenant_id"] == tenant["id"]

    login = client.post(
        "/api/v1/auth/login",
        data={"username": f"portal{n}", "password": "PortalPass123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/v1/portal/me", headers=headers).json()
    assert me["tenant_code"] == tenant["code"]

    # Platform API blocked
    blocked = client.get("/api/v1/devices", headers=headers)
    assert blocked.status_code == 403


def test_portal_sees_only_own_circuits(client, auth_headers):
    n = next(_seq)
    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": f"P DC {n}", "code": f"PDC{n}", "bgp_asn": 65001},
    ).json()
    t1 = client.post(
        "/api/v1/tenants",
        headers=auth_headers,
        json={"name": f"T1 {n}", "code": f"T1{n}"},
    ).json()
    t2 = client.post(
        "/api/v1/tenants",
        headers=auth_headers,
        json={"name": f"T2 {n}", "code": f"T2{n}"},
    ).json()
    dev = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"P-LEAF-{n}",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "mgmt_ip": f"10.5.{n}.1",
            "site_id": site["id"],
        },
        params={"learn": False},
    ).json()
    c1 = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "C1",
            "tenant_id": t1["id"],
            "bandwidth_mbps": 100,
            "endpoints": [{"label": "A", "device_id": dev["id"], "interface_name": "GE1/0/1"}],
        },
    ).json()
    client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "C2",
            "tenant_id": t2["id"],
            "bandwidth_mbps": 200,
            "endpoints": [{"label": "A", "device_id": dev["id"], "interface_name": "GE1/0/2"}],
        },
    )
    client.post(
        f"/api/v1/tenants/{t1['id']}/users",
        headers=auth_headers,
        json={"username": f"u1{n}", "password": "PortalPass123", "role": "tenant_viewer"},
    )
    token = client.post(
        "/api/v1/auth/login",
        data={"username": f"u1{n}", "password": "PortalPass123"},
    ).json()["access_token"]
    ph = {"Authorization": f"Bearer {token}"}

    circuits = client.get("/api/v1/portal/circuits", headers=ph).json()
    assert len(circuits) == 1
    assert circuits[0]["id"] == c1["id"]

    other = client.get(f"/api/v1/portal/circuits/{c1['id'] + 999}", headers=ph)
    assert other.status_code == 404
