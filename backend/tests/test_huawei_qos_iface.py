"""Huawei QoS rate-limit format, teardown recovery/log, and interface descriptions."""
from __future__ import annotations


def _huawei_topology(client, auth_headers, tag: str):
    site = client.post(
        "/api/v1/sites", headers=auth_headers,
        json={"name": f"HW DC {tag}", "code": f"HW{tag}", "city": "SH"},
    ).json()
    tenant = client.post(
        "/api/v1/tenants", headers=auth_headers,
        json={"name": "SDWAN-BACKBONE", "code": f"SD{tag}", "tenant_type": "enterprise"},
    ).json()
    dev = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={
            "name": f"hw-leaf-{tag}", "vendor": "huawei", "role": "leaf",
            "overlay_tech": "vxlan_evpn", "mgmt_ip": f"10.91.0.{tag}",
            "site_id": site["id"], "bgp_asn": 65010, "loopback_ip": f"10.91.255.{tag}",
        },
    ).json()
    return tenant, dev


def _make_circuit(client, auth_headers, tenant, dev, iface, bw=45):
    return client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={
            "name": "HW L2", "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn", "bandwidth_mbps": bw,
            "endpoints": [
                {"label": "A", "device_id": dev["id"], "interface_name": iface},
            ],
        },
    ).json()


def test_huawei_qos_matches_template(client, auth_headers):
    tenant, dev = _huawei_topology(client, auth_headers, "41")
    circuit = _make_circuit(client, auth_headers, tenant, dev, "GE1/0/11", bw=45)

    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    assert wo["status"] == "completed"
    cfg = "\n".join(j["rendered_config"] for j in wo["config_jobs"])

    # Shared ANY classifier (match-any), per-circuit behavior with car cir kbps,
    # per-circuit policy referencing ANY + behavior, precedence 5.
    assert "traffic classifier ANY type or" in cfg
    assert "if-match any" in cfg
    assert "car cir 46080 kbps" in cfg  # 45 * 1024
    assert "traffic behavior tb-" in cfg
    assert "classifier ANY behavior tb-" in cfg
    assert "precedence 5" in cfg
    # Old format must be gone, and Huawei has no MTU config.
    assert "cbs" not in cfg
    assert "mtu" not in cfg.lower()


def test_huawei_bandwidth_change_updates_behavior(client, auth_headers):
    tenant, dev = _huawei_topology(client, auth_headers, "42")
    circuit = _make_circuit(client, auth_headers, tenant, dev, "GE1/0/12", bw=45)
    client.post(f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers)

    # Change bandwidth -> 100M and re-provision (MODIFY).
    client.patch(
        f"/api/v1/circuits/{circuit['id']}", headers=auth_headers,
        json={"bandwidth_mbps": 100},
    )
    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}?wo_type=modify",
        headers=auth_headers,
    ).json()
    cfg = "\n".join(j["rendered_config"] for j in wo["config_jobs"])
    # Only the behavior's car cir reflects the new rate (100 * 1024 = 102400).
    assert "car cir 102400 kbps" in cfg
    assert "traffic behavior tb-" in cfg


def test_huawei_teardown_recovers_and_logs(client, auth_headers):
    tenant, dev = _huawei_topology(client, auth_headers, "43")
    circuit = _make_circuit(client, auth_headers, tenant, dev, "GE1/0/13", bw=45)
    client.post(f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers)

    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}?wo_type=decommission",
        headers=auth_headers,
    ).json()
    assert wo["status"] == "completed"
    cfg = "\n".join(j["rendered_config"] for j in wo["config_jobs"])
    # QoS objects recovered; shared ANY classifier deliberately kept.
    assert "undo traffic policy tp-" in cfg
    assert "undo traffic behavior tb-" in cfg
    assert "undo traffic classifier" not in cfg
    # Teardown process is logged like provisioning.
    messages = "\n".join(e["message"] for e in wo.get("events", []))
    assert "回收配置" in messages
    assert "undo" in messages


def test_bulk_interface_descriptions(client, auth_headers):
    _, dev = _huawei_topology(client, auth_headers, "44")
    r = client.post(
        f"/api/v1/devices/{dev['id']}/interfaces/descriptions",
        headers=auth_headers,
        json={
            "items": [
                {"name": "GE1/0/14", "description": "SDWAN-BACKBONE"},
                {"name": "GE1/0/14.100", "description": "SDWAN-BACKBONE:CIR-DD02B7"},
            ],
            "push": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["updated"] == 2
    assert body["dry_run"] is True  # tests run in dry-run
    assert "interface GE1/0/14" in body["rendered"]
    assert "description SDWAN-BACKBONE" in body["rendered"]

    # Persisted on the physical port.
    ifaces = client.get(
        f"/api/v1/devices/{dev['id']}/interfaces", headers=auth_headers
    ).json()
    by_name = {i["name"]: i for i in ifaces}
    assert by_name["GE1/0/14"]["description"] == "SDWAN-BACKBONE"


def test_clear_interface_description(client, auth_headers):
    _, dev = _huawei_topology(client, auth_headers, "45")
    client.post(
        f"/api/v1/devices/{dev['id']}/interfaces/descriptions",
        headers=auth_headers,
        json={"items": [{"name": "GE1/0/15", "description": "OLD"}], "push": True},
    )
    r = client.post(
        f"/api/v1/devices/{dev['id']}/interfaces/descriptions",
        headers=auth_headers,
        json={"items": [{"name": "GE1/0/15", "description": ""}], "push": True},
    ).json()
    assert "undo description" in r["rendered"]


def test_h3c_vlan_description_quoted(client, auth_headers):
    site = client.post(
        "/api/v1/sites", headers=auth_headers,
        json={"name": "TYO VLAN", "code": "TVQ99", "city": "TYO"},
    ).json()
    dev = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={
            "name": "h3c-vlan-q-99", "vendor": "h3c", "role": "pe",
            "overlay_tech": "vxlan_evpn", "mgmt_ip": "10.88.110.99",
            "site_id": site["id"], "bgp_asn": 65010, "loopback_ip": "10.88.255.99",
        },
    ).json()
    assert "id" in dev, dev
    r = client.post(
        f"/api/v1/devices/{dev['id']}/interfaces/descriptions",
        headers=auth_headers,
        json={
            "items": [{
                "name": "Vlan-interface2600",
                "description": "BB:P1:d(cs-1.tyo2):cm(pl-bb)",
            }],
            "push": True,
        },
    )
    assert r.status_code == 200, r.text
    rendered = r.json()["rendered"]
    assert "interface Vlan-interface2600" in rendered
    assert 'description "BB:P1:d(cs-1.tyo2):cm(pl-bb)"' in rendered


def test_parallel_bulk_interface_descriptions(client, auth_headers):
    _, dev_a = _huawei_topology(client, auth_headers, "46")
    _, dev_b = _huawei_topology(client, auth_headers, "47")
    r = client.post(
        "/api/v1/devices/interfaces/descriptions/bulk",
        headers=auth_headers,
        json={
            "push": True,
            "devices": [
                {
                    "device_id": dev_a["id"],
                    "items": [{"name": "GE1/0/16", "description": "SDWAN-A"}],
                },
                {
                    "device_id": dev_b["id"],
                    "items": [{"name": "GE1/0/17", "description": "SDWAN-B"}],
                },
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_updated"] == 2
    assert len(body["results"]) == 2
    assert all(item["dry_run"] is True for item in body["results"])
