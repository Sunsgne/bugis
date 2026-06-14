"""End-to-end API tests covering the provisioning pipeline."""
from __future__ import annotations

import itertools

_seq = itertools.count(1)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_requires_auth(client):
    assert client.get("/api/v1/tenants").status_code == 401


def test_drivers_catalog(client, auth_headers):
    r = client.get("/api/v1/drivers", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert set(data["vendors"]) == {"h3c", "huawei", "juniper", "arista", "cisco"}
    assert "vxlan_evpn" in data["overlay_tech"]
    assert "srmpls_evpn" in data["overlay_tech"]


def _bootstrap_topology(client, auth_headers):
    n = next(_seq)
    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": f"Test DC {n}", "code": f"T-DC{n}", "bgp_asn": 65010},
    ).json()
    tenant = client.post(
        "/api/v1/tenants",
        headers=auth_headers,
        json={"name": f"Test Tenant {n}", "code": f"T-TEN{n}", "type": "enterprise"},
    ).json()
    dev_a = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"T-H3C-{n}", "vendor": "h3c", "role": "leaf",
            "overlay_tech": "vxlan_evpn", "status": "online",
            "mgmt_ip": f"10.10.{n}.1", "bgp_asn": 65010, "site_id": site["id"],
        },
    ).json()
    dev_z = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"T-CSCO-{n}", "vendor": "cisco", "role": "pe",
            "overlay_tech": "srmpls_evpn", "status": "online",
            "mgmt_ip": f"10.10.{n}.2", "bgp_asn": 65010, "site_id": site["id"],
        },
    ).json()
    return site, tenant, dev_a, dev_z


def test_circuit_provisioning_pipeline(client, auth_headers):
    _, tenant, dev_a, dev_z = _bootstrap_topology(client, auth_headers)

    circuit = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "E2E L2VPN", "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn", "bandwidth_mbps": 500,
            "endpoints": [
                {"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/1"},
                {"label": "Z", "device_id": dev_z["id"], "interface_name": "GE1/0/1"},
            ],
        },
    ).json()
    # Auto-allocation should have filled identifiers.
    assert circuit["vni"] is not None
    assert circuit["route_distinguisher"]
    assert circuit["route_target"]
    assert circuit["status"] == "draft"

    # One-shot provision.
    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    assert wo["status"] == "completed"
    assert len(wo["config_jobs"]) >= 2
    # dry-run jobs succeed
    assert all(j["status"] == "dry_run" for j in wo["config_jobs"])
    # H3C config should contain a VSI, Cisco config an EVI.
    configs = "\n".join(j["rendered_config"] for j in wo["config_jobs"])
    assert "vsi vsi_" in configs
    assert "evpn" in configs

    # Circuit becomes active.
    refreshed = client.get(
        f"/api/v1/circuits/{circuit['id']}", headers=auth_headers
    ).json()
    assert refreshed["status"] == "active"


def test_telemetry_and_health(client, auth_headers):
    _, tenant, dev_a, dev_z = _bootstrap_topology(client, auth_headers)
    circuit = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "Mon circuit", "tenant_id": tenant["id"],
            "service_type": "l3vpn_evpn", "bandwidth_mbps": 1000,
            "sla_target": "99.99",
            "endpoints": [
                {"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/2"},
            ],
        },
    ).json()
    client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    )
    client.post("/api/v1/telemetry/simulate", headers=auth_headers)

    health = client.get(
        f"/api/v1/telemetry/circuits/{circuit['id']}/health", headers=auth_headers
    ).json()
    assert health["samples"] >= 1
    assert 0 <= health["health_score"] <= 100
