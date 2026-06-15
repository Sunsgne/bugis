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


def test_offering_prefill(client, auth_headers):
    _, tenant, dev_a, _ = _bootstrap_topology(client, auth_headers)
    n = next(_seq)
    offering = client.post(
        "/api/v1/offerings",
        headers=auth_headers,
        json={"name": "Gold", "code": f"GOLD-{n}", "service_type": "l3vpn_evpn",
              "bandwidth_mbps": 5000, "sla_target": "99.99", "cos": "ef", "tier": "gold"},
    ).json()
    circuit = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "From offering", "tenant_id": tenant["id"],
            "offering_id": offering["id"],
            "endpoints": [
                {"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/6",
                 "gateway_ip": "192.168.5.1"},
            ],
        },
    ).json()
    assert circuit["service_type"] == "l3vpn_evpn"
    assert circuit["bandwidth_mbps"] == 5000
    assert circuit["sla_target"] == "99.99"


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
    assert "500" in diff["diff"]  # new bandwidth appears in the diff


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
    # Discover interfaces via SNMP (simulated in dry-run).
    r = client.post(
        f"/api/v1/devices/{dev['id']}/discover-interfaces", headers=auth_headers
    )
    assert r.status_code == 200
    ifaces = r.json()
    assert len(ifaces) > 0
    # Huawei naming convention discovered
    assert any(i["name"].startswith("GE1/0/") for i in ifaces)
    assert all(i["discovered_via"] for i in ifaces)
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
    r = client.get("/api/v1/stream/events?token=invalid")
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
                  {"label": "A", "device_id": dev_h3c["id"], "interface_name": "GE1/0/1"},
                  {"label": "Z", "device_id": huawei["id"], "interface_name": "GE1/0/1"},
              ]},
    ).json()
    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    cfgs = {j["device_id"]: j["rendered_config"] for j in wo["config_jobs"]}
    h3c = cfgs[dev_h3c["id"]]
    hw = cfgs[huawei["id"]]
    # H3C CAR in kbps (200 Mbps -> 200000 kbps), inside service-instance
    assert "qos car inbound any cir 200000" in h3c
    si = h3c.index("service-instance")
    car = h3c.index("qos car")
    xconn = h3c.index("xconnect")
    assert si < car < xconn
    assert h3c.index("encapsulation") < car
    # Huawei line-rate qos lr in kbps with direction keyword
    assert "qos lr cir 200000 inbound" in hw
    assert "qos lr cir 200000 outbound" in hw
    # old bogus syntax gone
    assert "traffic policy" not in hw


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
    assert h3c.index("service-instance") < h3c.index("qos car") < h3c.index("xconnect")

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
    client.post("/api/v1/telemetry/simulate", headers=auth_headers)

    health = client.get(
        f"/api/v1/telemetry/circuits/{circuit['id']}/health", headers=auth_headers
    ).json()
    assert health["samples"] >= 1
    assert 0 <= health["health_score"] <= 100
