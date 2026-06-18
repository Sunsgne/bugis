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


def test_change_password(client, auth_headers):
    assert client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers,
        json={"current_password": "admin123", "new_password": "newpass12"},
    ).status_code == 204
    assert client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"},
    ).status_code == 401
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "newpass12"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "newpass12", "new_password": "admin123"},
    ).status_code == 204


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
    assert wo["circuit_status"] == "active"
    assert wo["config_jobs"][0].get("device_name") == "WB-FRR-1"
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


def test_decommission_clears_active_alarms(client, auth_headers):
    _, tenant, dev_a, _ = _bootstrap_topology(client, auth_headers)
    circuit = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "Alarm teardown", "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn", "bandwidth_mbps": 1000,
            "endpoints": [
                {"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/10"},
            ],
        },
    ).json()
    client.post(f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers)

    for _ in range(3):
        client.post(
            "/api/v1/telemetry/samples",
            headers=auth_headers,
            json={"circuit_id": circuit["id"], "packet_loss_pct": 5.0,
                  "latency_ms": 99, "utilization_pct": 98},
        )
    client.post("/api/v1/alarms/evaluate", headers=auth_headers)
    before = client.get(
        "/api/v1/alarms?status=active", headers=auth_headers
    ).json()
    assert [a for a in before if a["circuit_id"] == circuit["id"]]

    client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}?wo_type=decommission",
        headers=auth_headers,
    )
    after = client.get(
        "/api/v1/alarms?status=active", headers=auth_headers
    ).json()
    assert not [a for a in after if a["circuit_id"] == circuit["id"]]


def test_capacity_and_topology(client, auth_headers):
    _, _, dev_a, dev_z = _bootstrap_topology(client, auth_headers)
    client.post(f"/api/v1/devices/{dev_a['id']}/discover-interfaces", headers=auth_headers)
    client.post(f"/api/v1/devices/{dev_z['id']}/discover-interfaces", headers=auth_headers)
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
    assert base.get("vni") is not None
    assert base.get("vsi_name") is not None

    # Duplicate VNI rejected at create time.
    dup_resp = client.post(
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
    )
    assert dup_resp.status_code == 409
    assert "VNI" in dup_resp.json()["detail"]

    # Duplicate VSI rejected at create time.
    vsi_resp = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "VSI dup", "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
            "vsi_name": base["vsi_name"],
            "endpoints": [
                {"label": "A", "device_id": dev_z["id"], "interface_name": "GE1/0/4"},
            ],
        },
    )
    assert vsi_resp.status_code == 409
    assert "VSI" in vsi_resp.json()["detail"]


def test_circuit_probe(client, auth_headers):
    _, tenant, dev_a, dev_z = _bootstrap_topology(client, auth_headers)
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "Probe", "tenant_id": tenant["id"],
              "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
              "endpoints": [
                  {"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/1"},
                  {"label": "Z", "device_id": dev_z["id"], "interface_name": "GE1/0/1"},
              ]},
    ).json()
    client.post(f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers)
    r = client.post(f"/api/v1/circuits/{circuit['id']}/probe", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "reachable" in body
    assert body.get("mode") == "simulated"
    assert body["hop_count"] == len(body["hops"]) >= 2
    # Probe recorded a telemetry sample.
    samples = client.get(
        f"/api/v1/telemetry/circuits/{circuit['id']}/samples", headers=auth_headers
    ).json()
    assert len(samples) >= 1


def test_config_history_and_diff(client, auth_headers):
    _, tenant, dev_a, _ = _bootstrap_topology(client, auth_headers)
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "Hist", "tenant_id": tenant["id"],
              "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
              "endpoints": [
                  {"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/4"}
              ]},
    ).json()
    # First provision.
    client.post(f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers)
    # Change bandwidth and re-provision (MODIFY) -> second version.
    client.patch(f"/api/v1/circuits/{circuit['id']}", headers=auth_headers,
                 json={"bandwidth_mbps": 500})
    client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}?wo_type=modify",
        headers=auth_headers,
    )

    hist = client.get(
        f"/api/v1/circuits/{circuit['id']}/config-history", headers=auth_headers
    ).json()
    dev_hist = next(d for d in hist["devices"] if d["device_id"] == dev_a["id"])
    assert len(dev_hist["versions"]) >= 2

    diff = client.get(
        f"/api/v1/circuits/{circuit['id']}/config-diff?device_id={dev_a['id']}",
        headers=auth_headers,
    ).json()
    assert diff["changed"] is True
    assert "car cir 512000" in diff["diff"]  # 500 Mbps -> 512000 kbps in QoS CAR


def test_replace_circuit_endpoints(client, auth_headers):
    _, tenant, dev_a, dev_z = _bootstrap_topology(client, auth_headers)
    circuit = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "Endpoint Swap",
            "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn",
            "bandwidth_mbps": 100,
            "endpoints": [
                {
                    "label": "A",
                    "device_id": dev_a["id"],
                    "interface_name": "GE1/0/1",
                    "vlan_id": 2001,
                },
                {
                    "label": "Z",
                    "device_id": dev_z["id"],
                    "interface_name": "GE1/0/1",
                    "vlan_id": 2001,
                },
            ],
        },
    ).json()
    client.post(f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers)

    previous = [
        {
            "label": "A",
            "device_id": dev_a["id"],
            "interface_name": "GE1/0/1",
            "vlan_id": 2001,
        },
        {
            "label": "Z",
            "device_id": dev_z["id"],
            "interface_name": "GE1/0/1",
            "vlan_id": 2001,
        },
    ]
    updated = client.put(
        f"/api/v1/circuits/{circuit['id']}/endpoints",
        headers=auth_headers,
        json={
            "endpoints": [
                {
                    "label": "A",
                    "device_id": dev_a["id"],
                    "interface_name": "GE1/0/2",
                    "vlan_id": 2001,
                },
                {
                    "label": "Z",
                    "device_id": dev_z["id"],
                    "interface_name": "GE1/0/2",
                    "vlan_id": 2001,
                },
            ],
        },
    ).json()
    assert len(updated["endpoints"]) == 2
    assert updated["endpoints"][0]["interface_name"] == "GE1/0/2"

    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}?wo_type=modify",
        headers=auth_headers,
        json={"previous_endpoints": previous},
    ).json()
    assert wo["type"] == "modify"
    jobs = wo["config_jobs"]
    remove_jobs = [j for j in jobs if j["operation"] == "remove"]
    apply_jobs = [j for j in jobs if j["operation"] == "apply"]
    assert len(remove_jobs) == 2
    assert len(apply_jobs) >= 2
    h3c_remove = next(j for j in remove_jobs if j["device_id"] == dev_a["id"])
    assert "GE1/0/1" in h3c_remove["rendered_config"]
    assert "undo service-instance" in h3c_remove["rendered_config"]
    assert "undo vsi" not in h3c_remove["rendered_config"]
    h3c_apply = next(j for j in apply_jobs if j["device_id"] == dev_a["id"])
    assert "GE1/0/2" in h3c_apply["rendered_config"]


def test_device_baseline_initialize(client, auth_headers):
    site, _, _, _ = _bootstrap_topology(client, auth_headers)
    n = next(_seq)
    # a route reflector so the baseline has an overlay peer
    rr = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"RR-{n}", "vendor": "huawei", "role": "spine",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": f"10.66.{n}.1", "loopback_ip": f"10.66.{n}.255",
              "bgp_asn": 65010, "is_route_reflector": True, "site_id": site["id"]},
    ).json()
    leaf = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"LEAF-{n}", "vendor": "huawei", "role": "leaf",
              "overlay_tech": "vxlan_evpn", "status": "unknown",
              "mgmt_ip": f"10.66.{n}.2", "loopback_ip": f"10.66.{n}.11",
              "bgp_asn": 65010, "site_id": site["id"]},
    ).json()
    # preview baseline
    bl = client.get(f"/api/v1/devices/{leaf['id']}/baseline", headers=auth_headers).json()
    assert "sysname" in bl["content"]  # huawei
    assert "bgp 65010" in bl["content"]
    assert rr["loopback_ip"] in bl["content"]  # RR overlay peer present
    # initialize (push + snapshot)
    init = client.post(f"/api/v1/devices/{leaf['id']}/initialize", headers=auth_headers).json()
    assert init["success"] and init["version"] >= 1
    snaps = client.get(f"/api/v1/config/devices/{leaf['id']}/snapshots", headers=auth_headers).json()
    assert any(s["source"] == "init" for s in snaps)
    # baseline appears in assembled running config
    running = client.get(f"/api/v1/config/devices/{leaf['id']}/running", headers=auth_headers).json()
    assert "baseline (init)" in running["content"]


def test_snmp_interface_discovery(client, auth_headers):
    site, _, _, _ = _bootstrap_topology(client, auth_headers)
    n = next(_seq)
    dev = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"DISC-{n}", "vendor": "huawei", "role": "leaf",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": f"10.55.{n}.1", "site_id": site["id"]},
    ).json()
    # Discover interfaces via SNMP (IF-MIB) and persist them.
    r = client.post(
        f"/api/v1/devices/{dev['id']}/discover-interfaces", headers=auth_headers
    )
    assert r.status_code == 200
    ifaces = r.json()
    assert len(ifaces) > 0
    # CE6881-style naming (10GE/100GE) from real SNMP or dry-run fallback
    assert any(
        i["name"].startswith("10GE1/0/") or i["name"].startswith("100GE1/0/")
        for i in ifaces
    )
    assert all(
        i["discovered_via"] in ("snmp", "snmp-sim", "running-config", "link-sync")
        for i in ifaces
    )
    # Listing returns the same set
    listed = client.get(
        f"/api/v1/devices/{dev['id']}/interfaces", headers=auth_headers
    ).json()
    assert len(listed) == len(ifaces)


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

    zip_r = client.get(
        f"/api/v1/work-orders/{wo['id']}/ansible/download", headers=auth_headers
    )
    assert zip_r.status_code == 200
    assert zip_r.headers["content-type"] == "application/zip"
    assert len(zip_r.content) > 100

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


def test_bugis_sdn_controller(client, auth_headers):
    # Built-in Bugis controller is auto-registered on startup.
    controllers = client.get("/api/v1/controllers", headers=auth_headers).json()
    ctrl = next(c for c in controllers if c["type"] == "bugis")
    assert ctrl["base_url"] == "internal://bugis"

    # Cannot manually add or delete the built-in controller.
    dup = client.post(
        "/api/v1/controllers", headers=auth_headers,
        json={"name": "Bugis", "type": "bugis", "base_url": "internal://bugis"},
    )
    assert dup.status_code == 400
    blocked = client.delete(f"/api/v1/controllers/{ctrl['id']}", headers=auth_headers)
    assert blocked.status_code == 400

    n = next(_seq)
    site = client.post(
        "/api/v1/sites", headers=auth_headers,
        json={"name": "SDN DC", "code": f"SDN-DC{n}", "bgp_asn": 65040,
              "delivery_mode": "controller", "controller_id": ctrl["id"]},
    ).json()
    tenant = client.post(
        "/api/v1/tenants", headers=auth_headers,
        json={"name": "SDN Tenant", "code": f"SDN-TEN{n}", "type": "internal"},
    ).json()
    da = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"SDN-VTEP-A{n}", "vendor": "frr", "role": "vtep",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": f"10.40.{n}.1", "loopback_ip": f"10.40.{n}.1",
              "bgp_asn": 65040, "site_id": site["id"]},
    ).json()
    dz = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"SDN-VTEP-Z{n}", "vendor": "frr", "role": "vtep",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": f"10.40.{n}.2", "loopback_ip": f"10.40.{n}.2",
              "bgp_asn": 65040, "site_id": site["id"]},
    ).json()
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "SDN L2", "tenant_id": tenant["id"],
              "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
              "endpoints": [
                  {"label": "A", "device_id": da["id"], "interface_name": "swp1"},
                  {"label": "Z", "device_id": dz["id"], "interface_name": "swp1"},
              ]},
    ).json()
    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    assert wo["status"] == "completed"
    # Controller produced a control-plane job + per-device data-plane jobs.
    assert any(j["transport"] == "controller:bugis" for j in wo["config_jobs"])

    # Control plane now has VTEPs and EVPN routes for this VNI.
    vteps = client.get("/api/v1/controller/vteps", headers=auth_headers).json()
    assert any(v["device_id"] == da["id"] for v in vteps)
    routes = client.get(
        f"/api/v1/controller/routes?vni={circuit['vni']}", headers=auth_headers
    ).json()
    types = {r["type"] for r in routes}
    assert "type3_imet" in types and "type2_mac_ip" in types
    status = client.get("/api/v1/controller/status", headers=auth_headers).json()
    assert status["route_count"] >= len(routes)
    assert status["version"]
    assert status["kind"] == "builtin"
    assert status["capabilities_ready"] == status["capabilities_total"] == 8
    assert all(c["status"] == "ready" for c in status["capabilities"])
    assert "cluster" in status

    # BGP sessions auto-created for VTEPs
    bgp = client.get("/api/v1/controller/bgp/sessions", headers=auth_headers).json()
    assert len(bgp) >= 2
    sync = client.post("/api/v1/controller/bgp/sync", headers=auth_headers).json()
    assert sync["synced"] >= 2

    cluster = client.get("/api/v1/controller/cluster", headers=auth_headers).json()
    assert cluster["leader"]
    assert len(cluster["nodes"]) >= 2

    dp = client.get("/api/v1/controller/dataplane/bindings", headers=auth_headers).json()
    assert any(b["state"] == "applied" for b in dp)


def test_controller_delegation(client, auth_headers):
    # Controller-managed site delegates provisioning to the controller NB API.
    ctrl = client.post(
        "/api/v1/controllers",
        headers=auth_headers,
        json={"name": "NCE", "type": "nce_fabric",
              "base_url": "https://nce.test"},
    ).json()
    n = next(_seq)
    site = client.post(
        "/api/v1/sites", headers=auth_headers,
        json={"name": "Ctrl DC", "code": f"CTRL-DC{n}", "bgp_asn": 65030,
              "delivery_mode": "controller", "controller_id": ctrl["id"]},
    ).json()
    assert site["delivery_mode"] == "controller"
    tenant = client.post(
        "/api/v1/tenants", headers=auth_headers,
        json={"name": "Ctrl Tenant", "code": f"CTRL-TEN{n}", "type": "internal"},
    ).json()
    dev = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"CTRL-LEAF-{n}", "vendor": "huawei", "role": "leaf",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": f"10.30.{n}.1", "bgp_asn": 65030, "site_id": site["id"]},
    ).json()
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "Ctrl L2", "tenant_id": tenant["id"],
              "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
              "endpoints": [
                  {"label": "A", "device_id": dev["id"], "interface_name": "GE1/0/1"}
              ]},
    ).json()
    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    assert wo["status"] == "completed"
    jobs = wo["config_jobs"]
    assert any(j["transport"].startswith("controller") for j in jobs)
    ctrl_job = next(j for j in jobs if j["transport"].startswith("controller"))
    assert "huawei-nce-fabric" in ctrl_job["rendered_config"]


def test_notification_channel_and_test_send(client, auth_headers):
    ch = client.post(
        "/api/v1/notifications",
        headers=auth_headers,
        json={"name": "NOC 钉钉", "type": "dingtalk",
              "url": "https://oapi.dingtalk.com/robot/send?access_token=x",
              "min_severity": "warning"},
    ).json()
    assert ch["type"] == "dingtalk"
    # Test send (dry-run) returns rendered payload.
    res = client.post(f"/api/v1/notifications/{ch['id']}/test", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["payload"]["msgtype"] == "text"


def test_bulk_csv_devices(client, auth_headers):
    site, _, _, _ = _bootstrap_topology(client, auth_headers)
    n = next(_seq)
    csv_text = (
        "name,vendor,model,role,overlay_tech,status,mgmt_ip,loopback_ip,"
        "bgp_asn,sr_node_sid,site_code\n"
        f"BULK-{n},frr,SONiC,leaf,vxlan_evpn,online,10.20.{n}.1,10.20.{n}.1,"
        f"65020,,{site['code']}\n"
    )
    r = client.post(
        "/api/v1/bulk/devices/import",
        headers=auth_headers,
        files={"file": ("d.csv", csv_text, "text/csv")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1

    exp = client.get("/api/v1/bulk/devices/export", headers=auth_headers)
    assert exp.status_code == 200
    assert f"BULK-{n}" in exp.text
    assert exp.headers["content-type"].startswith("text/csv")


def test_sse_requires_valid_token(client):
    r = client.get("/api/v1/stream/events?ticket=invalid")
    assert r.status_code == 401


def test_system_info_and_scheduler_tick(client, auth_headers):
    info = client.get("/api/v1/system/info", headers=auth_headers)
    assert info.status_code == 200
    assert "scheduler" in info.json()
    # Manual scheduler tick runs telemetry + alarm evaluation.
    tick = client.post("/api/v1/system/scheduler/tick", headers=auth_headers)
    assert tick.status_code == 200
    assert "generated" in tick.json()


def test_access_encapsulation_modes(client, auth_headers):
    site, tenant, dev_h3c, dev_hw = _bootstrap_topology(client, auth_headers)
    # dev_h3c is H3C, dev_hw is Cisco in the helper; add a real Huawei device.
    huawei = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"HW-{next(_seq)}", "vendor": "huawei", "role": "leaf",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": "10.77.0.1", "bgp_asn": 65010, "site_id": site["id"]},
        params={"learn": False},
    ).json()

    # QinQ on H3C + untagged(access) on Huawei.
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "AC modes", "tenant_id": tenant["id"],
              "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
              "endpoints": [
                  {"label": "A", "device_id": dev_h3c["id"], "interface_name": "GE1/0/1",
                   "access_mode": "qinq", "vlan_id": 100, "inner_vlan_id": 200},
                  {"label": "Z", "device_id": huawei["id"], "interface_name": "GE1/0/1",
                   "access_mode": "access"},
              ]},
    ).json()
    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    cfgs = {j["device_id"]: j["rendered_config"] for j in wo["config_jobs"]}
    h3c_cfg = cfgs[dev_h3c["id"]]
    hw_cfg = cfgs[huawei["id"]]
    # H3C QinQ -> service-instance with s-vid + c-vid
    assert "service-instance" in h3c_cfg
    assert "encapsulation s-vid 100 c-vid 200" in h3c_cfg
    # Huawei access (untagged) -> sub-interface mode l2 + encapsulation untag
    assert ".mode l2" not in hw_cfg  # subif uses "<if>.<id> mode l2"
    assert "mode l2" in hw_cfg
    assert "encapsulation untag" in hw_cfg


def test_rate_limit_rendering(client, auth_headers):
    site, tenant, dev_h3c, _ = _bootstrap_topology(client, auth_headers)
    huawei = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"HW-RL-{next(_seq)}", "vendor": "huawei", "role": "leaf",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": "10.88.0.1", "bgp_asn": 65010, "site_id": site["id"]},
    ).json()
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "RL", "tenant_id": tenant["id"], "service_type": "l2vpn_evpn",
              "bandwidth_mbps": 200,
              "endpoints": [
                  {"label": "A", "device_id": dev_h3c["id"], "interface_name": "GE1/0/7"},
                  {"label": "Z", "device_id": huawei["id"], "interface_name": "GE1/0/7"},
              ]},
    ).json()
    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    cfgs = {j["device_id"]: j["rendered_config"] for j in wo["config_jobs"]}
    h3c = cfgs[dev_h3c["id"]]
    hw = cfgs[huawei["id"]]
    # H3C: classifier/behavior/policy globals + qos apply on service-instance (not VSI)
    assert "traffic classifier tc-" in h3c
    assert "car cir 204800 cbs 12800000" in h3c  # 200 Mbps * 1024 / * 64000
    assert "qos policy qp-" in h3c
    assert "qos apply policy qp-" in h3c
    assert "qos car inbound" not in h3c
    assert "(cid=" in h3c
    assert "(tenant=" not in h3c
    assert "mtu 9000" in h3c or "mtu 1500" in h3c
    vsi = h3c.index("vsi ")
    apply = h3c.index("qos apply policy")
    si = h3c.index("service-instance")
    assert vsi < si < apply
    assert "encapsulation s-vid" in h3c[si:]
    # Huawei: shared ANY classifier + per-circuit behavior/policy; traffic-policy
    # bound on the L2 sub-interface (现网惯例).
    assert "traffic classifier ANY type or" in hw
    assert "traffic policy tp-" in hw
    assert "traffic-policy tp-" in hw
    assert "classifier ANY behavior tb-" in hw
    # VRP8/CE applies the default color action automatically; the rendered car
    # line carries only 'cir <kbps> kbps' (no cbs).
    hw_car = next(l.strip() for l in hw.splitlines() if l.strip().startswith("car cir"))
    assert hw_car == "car cir 204800 kbps", hw_car
    assert "cbs" not in hw
    assert "qos lr cir" not in hw
    bd = hw.index("bridge-domain")
    subif = hw.index("interface GE1/0/7")
    tp = hw.index("traffic-policy tp-")
    assert bd < subif < tp
    assert "traffic-policy tp-" not in hw[bd:subif]


def test_h3c_huawei_template_quality(client, auth_headers):
    """Production-style checks for H3C/Huawei EVPN VXLAN templates."""
    site, tenant, dev_h3c, _ = _bootstrap_topology(client, auth_headers)
    huawei = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"HW-TPL-{next(_seq)}", "vendor": "huawei", "role": "leaf",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": "10.99.0.1", "bgp_asn": 65010, "site_id": site["id"]},
    ).json()
    l3 = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "L3 tpl", "tenant_id": tenant["id"],
              "service_type": "l3vpn_evpn", "bandwidth_mbps": 500,
              "endpoints": [
                  {"label": "A", "device_id": dev_h3c["id"], "interface_name": "GE1/0/3",
                   "vlan_id": 11, "gateway_ip": "10.11.0.1"},
              ]},
    ).json()
    wo = client.post(
        f"/api/v1/work-orders/provision/{l3['id']}", headers=auth_headers
    ).json()
    h3c = next(j["rendered_config"] for j in wo["config_jobs"] if j["device_id"] == dev_h3c["id"])
    assert "gateway vsi-interface Vsi-interface" in h3c
    assert "distributed-gateway local" in h3c
    assert "statistics enable" in h3c
    vsi = h3c.index("vsi ")
    apply = h3c.index("qos apply policy")
    si = h3c.index("service-instance")
    assert vsi < si < apply
    assert "(cid=" in h3c

    l2 = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "L2 access", "tenant_id": tenant["id"],
              "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
              "endpoints": [
                  {"label": "Z", "device_id": huawei["id"], "interface_name": "GE1/0/8",
                   "access_mode": "access"},
              ]},
    ).json()
    wo2 = client.post(
        f"/api/v1/work-orders/provision/{l2['id']}", headers=auth_headers
    ).json()
    hw_cfg = next(j["rendered_config"] for j in wo2["config_jobs"] if j["device_id"] == huawei["id"])
    assert "interface GE1/0/8 mode l2" in hw_cfg
    assert "GE1/0/8." not in hw_cfg
    assert "encapsulation untag" in hw_cfg
    assert "head-end peer-list protocol bgp" in hw_cfg
    bd = hw_cfg.index("bridge-domain")
    subif = hw_cfg.index("interface GE1/0/8")
    tp = hw_cfg.index("traffic-policy tp-")
    assert bd < subif < tp
    assert "traffic-policy tp-" not in hw_cfg[bd:subif]
    # VRP8 bridge-domain view has no 'mtu' command (rejected on real CE gear),
    # so the rendered BD section must not emit one.
    assert " mtu " not in hw_cfg.split("bridge-domain", 1)[1].split("interface", 1)[0]


def test_srmpls_vendor_template_quality(client, auth_headers):
    """Production-style checks for Juniper / Arista / Cisco SR-MPLS EVPN templates."""
    site, tenant, _, dev_cisco = _bootstrap_topology(client, auth_headers)
    n = next(_seq)
    dev_juniper = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"JUN-TPL-{n}", "vendor": "juniper", "role": "pe",
              "overlay_tech": "srmpls_evpn", "status": "online",
              "mgmt_ip": f"10.88.{n}.1", "loopback_ip": f"10.88.{n}.255",
              "bgp_asn": 65010, "sr_node_sid": 100 + n, "site_id": site["id"]},
    ).json()
    dev_arista = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"ARI-TPL-{n}", "vendor": "arista", "role": "pe",
              "overlay_tech": "srmpls_evpn", "status": "online",
              "mgmt_ip": f"10.89.{n}.1", "loopback_ip": f"10.89.{n}.255",
              "bgp_asn": 65010, "sr_node_sid": 200 + n, "site_id": site["id"]},
    ).json()

    l2 = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "SR-MPLS L2", "tenant_id": tenant["id"],
              "service_type": "l2vpn_evpn", "bandwidth_mbps": 200,
              "endpoints": [
                  {"label": "A", "device_id": dev_juniper["id"], "interface_name": "ge-0/0/1",
                   "vlan_id": 120},
                  {"label": "Z", "device_id": dev_cisco["id"], "interface_name": "GigabitEthernet0/0/0/1",
                   "vlan_id": 120},
              ]},
    ).json()
    wo = client.post(
        f"/api/v1/work-orders/provision/{l2['id']}", headers=auth_headers
    ).json()
    jun_cfg = next(j["rendered_config"] for j in wo["config_jobs"] if j["device_id"] == dev_juniper["id"])
    cisco_cfg = next(j["rendered_config"] for j in wo["config_jobs"] if j["device_id"] == dev_cisco["id"])
    assert "instance-type evpn" in jun_cfg
    assert "encapsulation vlan-bridge" in jun_cfg
    assert "label-allocation per-instance" in jun_cfg
    assert "l2vpn" in cisco_cfg and "bridge-domain BD_" in cisco_cfg
    assert "evpn" in cisco_cfg and "advertise-mac" in cisco_cfg
    assert "rewrite ingress tag pop 1 symmetric" in cisco_cfg

    l3 = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "SR-MPLS L3", "tenant_id": tenant["id"],
              "service_type": "l3vpn_evpn", "bandwidth_mbps": 300,
              "endpoints": [
                  {"label": "A", "device_id": dev_arista["id"], "interface_name": "Ethernet1",
                   "vlan_id": 130, "gateway_ip": "10.130.0.1"},
              ]},
    ).json()
    wo3 = client.post(
        f"/api/v1/work-orders/provision/{l3['id']}", headers=auth_headers
    ).json()
    ari_cfg = next(j["rendered_config"] for j in wo3["config_jobs"] if j["device_id"] == dev_arista["id"])
    assert "interface Vlan130" in ari_cfg
    assert "route-target import evpn" in ari_cfg
    assert "encapsulation mpls" in ari_cfg


def test_frr_template_quality(client, auth_headers):
    """FRR EVPN-VXLAN should render real bridge/vxlan dataplane, not comment-only stubs."""
    site = client.post(
        "/api/v1/sites", headers=auth_headers,
        json={"name": "FRR TPL DC", "code": f"FRR-TPL-{next(_seq)}", "bgp_asn": 65099},
    ).json()
    tenant = client.post(
        "/api/v1/tenants", headers=auth_headers,
        json={"name": "FRR TPL Tenant", "code": "FRR-TPL-T", "type": "internal"},
    ).json()
    dev = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": "FRR-TPL-1", "vendor": "frr", "role": "leaf",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": "10.9.9.1", "loopback_ip": "10.9.9.255",
              "bgp_asn": 65099, "site_id": site["id"]},
    ).json()
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "FRR dot1q", "tenant_id": tenant["id"],
              "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
              "endpoints": [
                  {"label": "A", "device_id": dev["id"], "interface_name": "swp1", "vlan_id": 50},
              ]},
    ).json()
    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    cfg = wo["config_jobs"][0]["rendered_config"]
    assert "bridge br" in cfg
    assert "interface vxlan" in cfg
    assert "encapsulation dot1q 50" in cfg
    assert "advertise-all-vni" in cfg
    assert "l2vpn evpn" in cfg
    assert "config vlan member" not in cfg  # no SONiC comment-only stub


def test_dot1q_default_encapsulation(client, auth_headers):
    site, tenant, dev_h3c, _ = _bootstrap_topology(client, auth_headers)
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "dot1q", "tenant_id": tenant["id"],
              "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
              "endpoints": [
                  {"label": "A", "device_id": dev_h3c["id"], "interface_name": "GE1/0/2",
                   "vlan_id": 300},
              ]},
    ).json()
    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    cfg = wo["config_jobs"][0]["rendered_config"]
    assert "encapsulation s-vid 300" in cfg
    assert "c-vid" not in cfg  # single-tag dot1q has no inner tag


def test_workorder_edit_cancel_delete(client, auth_headers):
    _, tenant, dev_a, _ = _bootstrap_topology(client, auth_headers)
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "WO mgmt", "tenant_id": tenant["id"], "service_type": "l2vpn_evpn",
              "endpoints": [{"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/1"}]},
    ).json()
    wo = client.post("/api/v1/work-orders", headers=auth_headers,
                     json={"circuit_id": circuit["id"], "type": "provision"}).json()
    # edit
    r = client.patch(f"/api/v1/work-orders/{wo['id']}", headers=auth_headers,
                     json={"title": "改标题", "notes": "备注"})
    assert r.status_code == 200 and r.json()["title"] == "改标题"
    # cancel
    assert client.post(f"/api/v1/work-orders/{wo['id']}/cancel", headers=auth_headers).json()["status"] == "cancelled"
    # delete
    assert client.delete(f"/api/v1/work-orders/{wo['id']}", headers=auth_headers).status_code == 204


def test_billing_95th(client, auth_headers):
    _, tenant, dev_a, _ = _bootstrap_topology(client, auth_headers)
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "bill", "tenant_id": tenant["id"], "service_type": "l2vpn_evpn",
              "bandwidth_mbps": 1000,
              "endpoints": [{"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/1"}]},
    ).json()
    client.post(f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers)
    for _ in range(20):
        client.post("/api/v1/telemetry/samples", headers=auth_headers,
                    json={"circuit_id": circuit["id"], "rx_mbps": 400, "tx_mbps": 600})
    b = client.get(f"/api/v1/telemetry/circuits/{circuit['id']}/billing", headers=auth_headers).json()
    assert b["billable_95_mbps"] > 0
    assert b["period"] and len(b["available_months"]) >= 1


def test_config_management(client, auth_headers):
    _, tenant, dev_a, _ = _bootstrap_topology(client, auth_headers)
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "cfg", "tenant_id": tenant["id"], "service_type": "l2vpn_evpn",
              "endpoints": [{"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/1"}]},
    ).json()
    # Provisioning auto-snapshots the device config.
    client.post(f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers)
    snaps = client.get(f"/api/v1/config/devices/{dev_a['id']}/snapshots", headers=auth_headers).json()
    assert len(snaps) >= 1 and snaps[0]["source"] == "push"
    running = client.get(f"/api/v1/config/devices/{dev_a['id']}/running", headers=auth_headers).json()
    assert "running-config" in running["content"]
    # manual backup creates a new version
    bk = client.post(f"/api/v1/config/devices/{dev_a['id']}/backup", headers=auth_headers).json()
    assert bk["version"] >= 2


def test_feishu_notification(client, auth_headers):
    ch = client.post("/api/v1/notifications", headers=auth_headers,
                     json={"name": "飞书群", "type": "feishu",
                           "url": "https://open.feishu.cn/open-apis/bot/v2/hook/x",
                           "min_severity": "warning"}).json()
    res = client.post(f"/api/v1/notifications/{ch['id']}/test", headers=auth_headers).json()
    assert res["success"] and res["payload"]["msg_type"] == "text"


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
    client.post(
        "/api/v1/telemetry/samples",
        headers=auth_headers,
        json={
            "circuit_id": circuit["id"],
            "rx_mbps": 120.0,
            "tx_mbps": 80.0,
            "latency_ms": 4.5,
            "jitter_ms": 0.3,
            "packet_loss_pct": 0.01,
            "tunnel_state": "up",
        },
    )

    health = client.get(
        f"/api/v1/telemetry/circuits/{circuit['id']}/health", headers=auth_headers
    ).json()
    assert health["samples"] >= 1
    assert 0 <= health["health_score"] <= 100


def test_circuit_monitoring_apis(client, auth_headers):
    _, tenant, dev_a, _ = _bootstrap_topology(client, auth_headers)
    circuit = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "Mon2", "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn", "bandwidth_mbps": 1000,
            "endpoints": [{"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/2"}],
        },
    ).json()
    client.post(f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers)
    for i in range(10):
        client.post(
            "/api/v1/telemetry/samples",
            headers=auth_headers,
            json={
                "circuit_id": circuit["id"],
                "rx_mbps": 100 + i,
                "tx_mbps": 200 + i,
                "latency_ms": 5 + i * 0.1,
                "jitter_ms": 0.5,
                "packet_loss_pct": 0.01,
                "tunnel_state": "down" if i == 5 else "up",
            },
        )

    traffic = client.get(
        f"/api/v1/telemetry/circuits/{circuit['id']}/traffic-summary?hours=24",
        headers=auth_headers,
    ).json()
    assert len(traffic["samples"]) >= 1
    assert traffic["p95"]["billable_95_mbps"] > 0

    avail = client.get(
        f"/api/v1/telemetry/circuits/{circuit['id']}/availability?hours=24",
        headers=auth_headers,
    ).json()
    assert "uptime_pct" in avail
    assert isinstance(avail["events"], list)

    from datetime import datetime, timedelta, timezone

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=2)
    custom = client.get(
        f"/api/v1/telemetry/circuits/{circuit['id']}/traffic-summary",
        headers=auth_headers,
        params={"start_at": start.isoformat(), "end_at": end.isoformat()},
    )
    assert custom.status_code == 200
    assert len(custom.json()["samples"]) >= 1

    custom_avail = client.get(
        f"/api/v1/telemetry/circuits/{circuit['id']}/availability",
        headers=auth_headers,
        params={"start_at": start.isoformat(), "end_at": end.isoformat()},
    )
    assert custom_avail.status_code == 200
    assert "uptime_pct" in custom_avail.json()

    health_window = client.get(
        f"/api/v1/telemetry/circuits/{circuit['id']}/health",
        headers=auth_headers,
        params={"hours": 24, "limit": 5},
    )
    assert health_window.status_code == 200
    body = health_window.json()
    assert body["samples"] <= 5


def test_delete_decommissioned_circuit(client, auth_headers):
    _, tenant, dev_a, _ = _bootstrap_topology(client, auth_headers)
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "to-delete", "tenant_id": tenant["id"], "service_type": "l2vpn_evpn",
              "endpoints": [{"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/1"}]},
    ).json()
    client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}?wo_type=decommission",
        headers=auth_headers,
    )
    refreshed = client.get(f"/api/v1/circuits/{circuit['id']}", headers=auth_headers).json()
    assert refreshed["status"] == "decommissioned"
    assert client.delete(
        f"/api/v1/circuits/{circuit['id']}", headers=auth_headers
    ).status_code == 204
    assert client.get(f"/api/v1/circuits/{circuit['id']}", headers=auth_headers).status_code == 404


def test_delete_active_circuit_forbidden(client, auth_headers):
    _, tenant, dev_a, _ = _bootstrap_topology(client, auth_headers)
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "active-no-del", "tenant_id": tenant["id"], "service_type": "l2vpn_evpn",
              "endpoints": [{"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/1"}]},
    ).json()
    client.post(f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers)
    r = client.delete(f"/api/v1/circuits/{circuit['id']}", headers=auth_headers)
    assert r.status_code == 409


def test_tenant_summaries(client, auth_headers):
    _, tenant, dev_a, _ = _bootstrap_topology(client, auth_headers)
    client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "sum-c", "tenant_id": tenant["id"], "service_type": "l2vpn_evpn",
              "bandwidth_mbps": 500,
              "endpoints": [{"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/1"}]},
    )
    summaries = client.get("/api/v1/tenants/summaries", headers=auth_headers).json()
    row = next(s for s in summaries if s["tenant_id"] == tenant["id"])
    assert row["circuits_total"] >= 1
    assert row["total_bandwidth_mbps"] >= 500
    one = client.get(f"/api/v1/tenants/{tenant['id']}/summary", headers=auth_headers).json()
    assert one["tenant_id"] == tenant["id"]


def test_tenant_list_pagination(client, auth_headers):
    r = client.get("/api/v1/tenants?page=1&page_size=10", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body

    overview = client.get("/api/v1/tenants/overview", headers=auth_headers).json()
    assert "tenants_total" in overview
    assert "circuits_total" in overview


def test_remote_ipt_provision(client, auth_headers):
    n = next(_seq)
    egress = client.post(
        "/api/v1/sites", headers=auth_headers,
        json={"name": f"US PoP {n}", "code": f"US-POP{n}", "region": "US", "bgp_asn": 65100},
    ).json()
    access = client.post(
        "/api/v1/sites", headers=auth_headers,
        json={"name": f"CN DC {n}", "code": f"CN-DC{n}", "region": "CN", "bgp_asn": 65101},
    ).json()
    tenant = client.post(
        "/api/v1/tenants", headers=auth_headers,
        json={"name": f"RIPT Tenant {n}", "code": f"RIPT{n}", "type": "enterprise"},
    ).json()
    border = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"US-BORDER-{n}", "vendor": "huawei", "role": "dci_gw",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": f"10.20.{n}.1", "bgp_asn": 65100, "site_id": egress["id"]},
    ).json()
    leaf = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"CN-LEAF-{n}", "vendor": "h3c", "role": "leaf",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": f"10.21.{n}.1", "bgp_asn": 65101, "site_id": access["id"]},
    ).json()
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={
            "name": "CN-US Remote IPT", "tenant_id": tenant["id"],
            "service_type": "remote_ipt", "bandwidth_mbps": 200,
            "egress_country": "US", "egress_site_id": egress["id"],
            "ipt_nat_enabled": 1,
            "endpoints": [{
                "label": "A", "device_id": leaf["id"], "interface_name": "GE1/0/5",
                "gateway_ip": "10.200.1.1", "vlan_id": 200,
            }],
        },
    ).json()
    assert circuit["ipt_public_ip"]
    v = client.get(f"/api/v1/circuits/{circuit['id']}/validate", headers=auth_headers).json()
    assert v["ok"]
    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    assert wo["status"] == "completed"
    configs = " ".join(j.get("rendered_config", "") for j in wo["config_jobs"])
    assert "REMOTE IPT" in configs or "Remote IPT" in configs or "remote_ipt" in configs.lower()
    assert circuit["code"] in configs or "vrf_" in configs


def test_link_bandwidth_from_port_description(client, auth_headers):
    n = next(_seq)
    site = client.post(
        "/api/v1/sites", headers=auth_headers,
        json={"name": f"DC {n}", "code": f"DC{n}", "bgp_asn": 65020},
    ).json()
    dev_a = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"BR-A-{n}", "vendor": "h3c", "role": "dci_gw",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": f"10.30.{n}.1", "bgp_asn": 65020, "site_id": site["id"]},
    ).json()
    dev_z = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"BR-Z-{n}", "vendor": "huawei", "role": "dci_gw",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": f"10.30.{n}.2", "bgp_asn": 65020, "site_id": site["id"]},
    ).json()
    link = client.post(
        "/api/v1/capacity/links", headers=auth_headers,
        json={
            "name": f"DCI-{n}", "type": "dci",
            "device_a_id": dev_a["id"], "device_z_id": dev_z["id"],
            "interface_a": "HundredGigE1/0/1", "interface_z": "HundredGE1/0/1",
            "capacity_mbps": 50000,
        },
    ).json()
    client.post(f"/api/v1/devices/{dev_a['id']}/discover-interfaces", headers=auth_headers)
    client.post(f"/api/v1/devices/{dev_z['id']}/discover-interfaces", headers=auth_headers)
    sync = client.post("/api/v1/capacity/links/sync-bandwidth", headers=auth_headers).json()
    assert sync["links"] >= 1
    usage = client.get("/api/v1/capacity/links/usage", headers=auth_headers).json()
    row = next(u for u in usage if u["link_id"] == link["id"])
    assert row["capacity_mbps"] == 100000
    from app.scheduler import run_once
    run_once()
    usage2 = client.get("/api/v1/capacity/links/usage", headers=auth_headers).json()
    row2 = next(u for u in usage2 if u["link_id"] == link["id"])
    assert row2["samples"] > 0
    assert row2["traffic_mbps"] > 0


def test_sr_explicit_circuit_path(client, auth_headers):
    n = next(_seq)
    site = client.post(
        "/api/v1/sites", headers=auth_headers,
        json={"name": f"SR DC {n}", "code": f"SR{n}", "bgp_asn": 65110},
    ).json()
    pe_a = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"PE-A-{n}", "vendor": "juniper", "role": "pe",
              "overlay_tech": "srmpls_evpn", "status": "online",
              "mgmt_ip": f"10.40.{n}.1", "bgp_asn": 65110, "site_id": site["id"],
              "sr_node_sid": 100, "loopback_ip": "10.255.1.1"},
    ).json()
    p_mid = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"P-MID-{n}", "vendor": "juniper", "role": "p",
              "overlay_tech": "srmpls_evpn", "status": "online",
              "mgmt_ip": f"10.40.{n}.2", "bgp_asn": 65110, "site_id": site["id"],
              "sr_node_sid": 200},
    ).json()
    pe_z = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"PE-Z-{n}", "vendor": "cisco", "role": "pe",
              "overlay_tech": "srmpls_evpn", "status": "online",
              "mgmt_ip": f"10.40.{n}.3", "bgp_asn": 65110, "site_id": site["id"],
              "sr_node_sid": 300, "loopback_ip": "10.255.1.3"},
    ).json()
    client.post(
        "/api/v1/capacity/links", headers=auth_headers,
        json={"name": f"A-P-{n}", "type": "dci",
              "device_a_id": pe_a["id"], "device_z_id": p_mid["id"],
              "interface_a": "xe-0/0/0", "interface_z": "xe-0/0/1",
              "capacity_mbps": 100000},
    )
    client.post(
        "/api/v1/capacity/links", headers=auth_headers,
        json={"name": f"P-Z-{n}", "type": "dci",
              "device_a_id": p_mid["id"], "device_z_id": pe_z["id"],
              "interface_a": "xe-0/0/2", "interface_z": "TenGigE0/0/0/1",
              "capacity_mbps": 100000},
    )
    preview = client.post(
        "/api/v1/circuits/path/preview", headers=auth_headers,
        json={
            "endpoint_device_ids": [pe_a["id"], pe_z["id"]],
            "via_device_ids": [p_mid["id"]],
            "path_mode": "explicit_sr",
        },
    ).json()
    assert preview["explicit_supported"] is True
    assert preview["segment_list"] == [100, 200, 300]

    tenant = client.post(
        "/api/v1/tenants", headers=auth_headers,
        json={"name": f"SR Tenant {n}", "code": f"SRT{n}", "type": "enterprise"},
    ).json()
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={
            "name": "SR explicit path circuit",
            "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn",
            "path_mode": "explicit_sr",
            "via_device_ids": [p_mid["id"]],
            "endpoints": [
                {"label": "A", "device_id": pe_a["id"], "interface_name": "ge-0/0/1"},
                {"label": "Z", "device_id": pe_z["id"], "interface_name": "GigabitEthernet0/0/0/1"},
            ],
        },
    ).json()
    assert circuit["path_mode"] == "explicit_sr"
    assert circuit["segment_list"] == [100, 200, 300]

    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    assert wo["status"] == "completed"
    configs = "\n".join(j.get("rendered_config", "") for j in wo["config_jobs"])
    assert "segment-list" in configs.lower() or "SR Policy" in configs or "segment-routing" in configs


def test_device_check_svid_scan(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.services.snmp.random.random", lambda: 0.99)

    dev = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={
            "name": "SH-PE-SCAN",
            "vendor": "cisco",
            "role": "pe",
            "overlay_tech": "srmpls_evpn",
            "status": "online",
            "mgmt_ip": "10.2.0.88",
            "sr_node_sid": 100,
        },
    ).json()
    client.post(f"/api/v1/devices/{dev['id']}/discover-interfaces", headers=auth_headers)

    r = client.post(f"/api/v1/devices/{dev['id']}/check", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["reachable"] is True
    assert data["svid_scan"] is not None

    # Simulate legacy S-VID on a port by renaming device to match legacy sim key
    client.patch(
        f"/api/v1/devices/{dev['id']}", headers=auth_headers,
        json={"name": "SH-PE-01"},
    )
    r2 = client.post(f"/api/v1/devices/{dev['id']}/check", headers=auth_headers)
    scan = r2.json()["svid_scan"]
    assert scan["total_s_vids"] >= 2

    ifaces = client.get(
        f"/api/v1/devices/{dev['id']}/interfaces", headers=auth_headers
    ).json()
    busy = [i for i in ifaces if i.get("used_s_vids")]
    assert busy

    tenant = client.post(
        "/api/v1/tenants", headers=auth_headers,
        json={"name": "SVid Tenant", "code": "SVID01", "type": "enterprise"},
    ).json()
    conflict = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={
            "name": "conflict line",
            "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn",
            "endpoints": [{
                "label": "A",
                "device_id": dev["id"],
                "interface_name": "GigabitEthernet0/0/0/2",
                "vlan_id": 150,
                "access_mode": "dot1q",
            }],
        },
    )
    assert conflict.status_code == 409


def test_snmp_settings_crud(client, auth_headers):
    r = client.get("/api/v1/system/snmp", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["community"]
    assert body["port"] == 161
    assert isinstance(body["exclude_name_patterns"], list)
    assert isinstance(body["include_name_patterns"], list)

    r2 = client.patch(
        "/api/v1/system/snmp",
        headers=auth_headers,
        json={"community": "test-ro", "timeout_sec": 3, "retries": 2},
    )
    assert r2.status_code == 200
    assert r2.json()["community"] == "test-ro"
    assert r2.json()["timeout_sec"] == 3

    devs = client.get("/api/v1/devices", headers=auth_headers).json()
    if devs["items"]:
        t = client.post(
            "/api/v1/system/snmp/test",
            headers=auth_headers,
            json={"device_id": devs["items"][0]["id"]},
        )
        assert t.status_code == 200
        assert t.json()["ok"] is True
        assert t.json()["interfaces_found"] > 0


def test_snmp_settings_null_patterns(client, auth_headers):
    from app.core.database import SessionLocal
    from app.models.snmp_settings import SnmpSettings

    db = SessionLocal()
    try:
        row = db.get(SnmpSettings, 1)
        assert row is not None
        row.exclude_name_patterns = None
        row.include_name_patterns = None
        db.commit()
    finally:
        db.close()

    r = client.get("/api/v1/system/snmp", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["exclude_name_patterns"], list)
    assert isinstance(body["include_name_patterns"], list)
    assert len(body["exclude_name_patterns"]) > 0


def test_platform_settings_crud(client, auth_headers):
    r = client.get("/api/v1/system/settings", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "platform" in body
    assert "readonly" in body
    assert body["platform"]["dry_run"] is True

    r2 = client.patch(
        "/api/v1/system/settings/platform",
        headers=auth_headers,
        json={
            "dry_run": False,
            "scheduler_interval_seconds": 60,
            "threshold_latency_ms": 80,
            "webhook_token": "test-token-xyz",
        },
    )
    assert r2.status_code == 200
    updated = r2.json()
    assert updated["dry_run"] is False
    assert updated["scheduler_interval_seconds"] == 60
    assert updated["threshold_latency_ms"] == 80
    assert updated["webhook_token"] == "test-token-xyz"

    status = client.get("/api/v1/system/settings/platform/status", headers=auth_headers)
    assert status.status_code == 200
    assert status.json()["dry_run"] is False


def test_list_pagination(client, auth_headers):
    """List endpoints return paginated envelopes for scale."""
    r = client.get("/api/v1/circuits?page=1&page_size=10", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body and body["page"] == 1

    r2 = client.get("/api/v1/devices?page=1&page_size=10", headers=auth_headers)
    assert r2.status_code == 200
    assert "items" in r2.json()

    r3 = client.get("/api/v1/tenants?page=1&page_size=10", headers=auth_headers)
    assert r3.status_code == 200
    assert "items" in r3.json()

    r4 = client.get("/api/v1/circuits?q=NONEXISTENT_CODE_XYZ", headers=auth_headers)
    assert r4.status_code == 200
    assert r4.json()["total"] == 0


