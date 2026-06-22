"""Tests for VNI-centric circuit adoption from whole-network learned config."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

_seq = itertools.count(1)


def _bootstrap(client: TestClient, headers: dict, *, name_suffix: str | None = None):
    n = next(_seq)
    suffix = name_suffix or str(n)
    site = client.post(
        "/api/v1/sites",
        headers=headers,
        json={"name": f"DC {suffix}", "code": f"DC{suffix}", "bgp_asn": 65010},
    ).json()
    tenant = client.post(
        "/api/v1/tenants",
        headers=headers,
        json={"name": f"T {suffix}", "code": f"TEN{suffix}", "type": "enterprise"},
    ).json()
    dev = client.post(
        "/api/v1/devices",
        headers=headers,
        json={
            "name": f"H3C-{suffix}",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "status": "online",
            "mgmt_ip": f"10.30.{n}.1",
            "bgp_asn": 65010,
            "site_id": site["id"],
        },
        params={"learn": "true"},
    ).json()
    return tenant, dev


def test_preview_adopt_by_vni_discovers_learned_endpoints(client, auth_headers):
    dev1 = _bootstrap(client, auth_headers, name_suffix="a")[1]
    dev2 = _bootstrap(client, auth_headers, name_suffix="b")[1]

    preview = client.get(
        "/api/v1/circuits/adopt-by-vni/preview",
        headers=auth_headers,
        params={"vni": 10001, "refresh_inventory": "true"},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["vni"] == 10001
    assert body["total_count"] >= 2
    assert body["adoptable_count"] >= 2
    assert body["can_adopt"] is True
    device_names = {ep["device_name"] for ep in body["endpoints"]}
    assert dev1["name"] in device_names
    assert dev2["name"] in device_names
    for ep in body["endpoints"]:
        assert ep["interface_name"]
        assert ep["access_mode"] in ("dot1q", "qinq", "access")


def test_adopt_circuit_from_vni_auto_associates_endpoints(client, auth_headers):
    tenant, dev1 = _bootstrap(client, auth_headers, name_suffix="c")
    _, dev2 = _bootstrap(client, auth_headers, name_suffix="d")

    adopted = client.post(
        "/api/v1/circuits/adopt-from-vni",
        headers=auth_headers,
        json={
            "name": "Imported by VNI",
            "tenant_id": tenant["id"],
            "vni": 10001,
            "refresh_inventory": True,
        },
    )
    assert adopted.status_code == 201, adopted.text
    body = adopted.json()
    assert body["adopted"] is True
    assert body["status"] == "active"
    assert body["vni"] == 10001
    assert len(body["endpoints"]) >= 2
    endpoint_devices = {ep["device_id"] for ep in body["endpoints"]}
    assert dev1["id"] in endpoint_devices
    assert dev2["id"] in endpoint_devices

    wo = client.post(
        f"/api/v1/work-orders/provision/{body['id']}",
        headers=auth_headers,
    ).json()
    assert wo["status"] == "completed"
    assert not wo.get("config_jobs")

    inventory = client.get("/api/v1/controller/overlay-inventory", headers=auth_headers).json()
    assert any(item.get("circuit_code") == body["code"] for item in inventory["items"])

    duplicate = client.post(
        "/api/v1/circuits/adopt-from-vni",
        headers=auth_headers,
        json={
            "name": "Duplicate VNI service",
            "tenant_id": tenant["id"],
            "vni": 10001,
            "refresh_inventory": True,
        },
    )
    assert duplicate.status_code == 409
