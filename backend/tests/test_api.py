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
    assert set(data["vendors"]) == {
        "h3c", "huawei", "juniper", "arista", "cisco", "frr"
    }
    assert "vxlan_evpn" in data["overlay_tech"]
    assert "srmpls_evpn" in data["overlay_tech"]


def test_frr_provisioning(client, auth_headers):
    site = client.post(
        "/api/v1/sites", headers=auth_headers,
        json={"name": "FRR DC", "code": "FRR-DC", "bgp_asn": 65099},
    ).json()
    tenant = client.post(
        "/api/v1/tenants", headers=auth_headers,
        json={"name": "FRR Tenant", "code": "FRR-TEN", "type": "internal"},
    ).json()
    dev = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": "WB-FRR-1", "vendor": "frr", "role": "leaf",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": "10.9.0.1", "bgp_asn": 65099, "site_id": site["id"]},
    ).json()
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "FRR L2", "tenant_id": tenant["id"],
              "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
              "endpoints": [
                  {"label": "A", "device_id": dev["id"], "interface_name": "swp1"}
              ]},
    ).json()
    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    assert wo["status"] == "completed"
    cfg = wo["config_jobs"][0]["rendered_config"]
    assert "advertise-all-vni" in cfg and "l2vpn evpn" in cfg
    # Ansible export uses vtysh for FRR.
    exp = client.get(f"/api/v1/work-orders/{wo['id']}/ansible", headers=auth_headers).json()
    assert "vtysh" in exp["playbook"]


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


def test_alarms_lifecycle(client, auth_headers):
    _, tenant, dev_a, _ = _bootstrap_topology(client, auth_headers)
    circuit = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "Alarm circuit", "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn", "bandwidth_mbps": 1000,
            "endpoints": [
                {"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/9"},
            ],
        },
    ).json()
    client.post(f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers)

    # Inject a breaching sample then evaluate.
    for _ in range(3):
        client.post(
            "/api/v1/telemetry/samples",
            headers=auth_headers,
            json={"circuit_id": circuit["id"], "packet_loss_pct": 5.0,
                  "latency_ms": 99, "utilization_pct": 98},
        )
    r = client.post("/api/v1/alarms/evaluate", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["active_alarms"] >= 1

    alarms = client.get(
        "/api/v1/alarms?status=active", headers=auth_headers
    ).json()
    circuit_alarms = [a for a in alarms if a["circuit_id"] == circuit["id"]]
    assert circuit_alarms
    # Acknowledge then clear.
    aid = circuit_alarms[0]["id"]
    assert client.post(f"/api/v1/alarms/{aid}/ack", headers=auth_headers, json={}).status_code == 200
    assert client.post(f"/api/v1/alarms/{aid}/clear", headers=auth_headers).status_code == 200


def test_capacity_and_topology(client, auth_headers):
    _, _, dev_a, dev_z = _bootstrap_topology(client, auth_headers)
    link = client.post(
        "/api/v1/capacity/links",
        headers=auth_headers,
        json={
            "name": "test-dci", "type": "dci",
            "device_a_id": dev_a["id"], "device_z_id": dev_z["id"],
            "capacity_mbps": 100000, "reserved_mbps": 5000,
        },
    )
    assert link.status_code == 201
    usage = client.get("/api/v1/capacity/links/usage", headers=auth_headers).json()
    assert any(u["name"] == "test-dci" for u in usage)
    topo = client.get("/api/v1/capacity/topology", headers=auth_headers).json()
    assert "nodes" in topo and "edges" in topo
    assert len(topo["nodes"]) >= 2


def test_validation_blocks_collision(client, auth_headers):
    _, tenant, dev_a, dev_z = _bootstrap_topology(client, auth_headers)
    base = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "VNI base", "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
            "endpoints": [
                {"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/3"},
            ],
        },
    ).json()
    # Second circuit forced onto the same VNI -> collision.
    dup = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "VNI dup", "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
            "vni": base["vni"],
            "endpoints": [
                {"label": "A", "device_id": dev_z["id"], "interface_name": "GE1/0/3"},
            ],
        },
    ).json()
    v = client.get(f"/api/v1/circuits/{dup['id']}/validate", headers=auth_headers).json()
    assert v["ok"] is False
    assert any(i["code"] == "vni_collision" for i in v["issues"])

    # Provisioning must be blocked by the pre-check.
    wo = client.post(
        f"/api/v1/work-orders/provision/{dup['id']}", headers=auth_headers
    ).json()
    assert wo["status"] == "failed"


def test_device_check(client, auth_headers):
    _, _, dev_a, _ = _bootstrap_topology(client, auth_headers)
    r = client.post(f"/api/v1/devices/{dev_a['id']}/check", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "reachable" in body and body["status"] in ("online", "offline")


def test_webhook_provision_and_ansible(client, auth_headers):
    _, tenant, dev_a, dev_z = _bootstrap_topology(client, auth_headers)
    # Webhook intake (StackStorm-style) with shared token.
    r = client.post(
        "/api/v1/integrations/webhook/provision",
        headers={"X-Webhook-Token": "bugis-webhook-token"},
        json={
            "tenant_code": tenant["code"],
            "name": "WH circuit",
            "service_type": "l2vpn_evpn",
            "bandwidth_mbps": 200,
            "endpoints": [
                {"label": "A", "device_name": dev_a["name"], "interface_name": "GE1/0/7"},
                {"label": "Z", "device_name": dev_z["name"], "interface_name": "GE1/0/7"},
            ],
        },
    )
    assert r.status_code == 201, r.text
    wo = r.json()
    assert wo["status"] == "completed"

    # Ansible export for the work order.
    exp = client.get(f"/api/v1/work-orders/{wo['id']}/ansible", headers=auth_headers)
    assert exp.status_code == 200
    data = exp.json()
    assert "h3c.comware" in data["inventory"]
    assert "tasks:" in data["playbook"]

    # Wrong webhook token (with valid body) is rejected.
    bad = client.post(
        "/api/v1/integrations/webhook/provision",
        headers={"X-Webhook-Token": "nope"},
        json={
            "tenant_code": tenant["code"], "name": "x",
            "endpoints": [
                {"label": "A", "device_name": dev_a["name"], "interface_name": "GE1/0/8"}
            ],
        },
    )
    assert bad.status_code == 401


def test_audit_log_records_mutations(client, auth_headers):
    # A create call should be captured in the audit log.
    client.post(
        "/api/v1/tenants",
        headers=auth_headers,
        json={"name": "Audit Tenant", "code": "AUDIT1", "type": "internal"},
    )
    logs = client.get("/api/v1/audit?limit=50", headers=auth_headers).json()
    assert any(
        l["path"] == "/api/v1/tenants" and l["method"] == "POST" for l in logs
    )


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
