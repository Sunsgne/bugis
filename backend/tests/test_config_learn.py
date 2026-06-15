"""Tests for live-network config auto-learn."""
from __future__ import annotations

import itertools

from app.core.database import SessionLocal
from app.models.device import Device
from app.models.enums import Vendor
from app.services import config_learn_parse, config_mgmt, port_inventory

_seq = itertools.count(1)

H3C_CONFIG = """\
sysname BJ-LEAF-01
interface LoopBack0
 ip address 10.1.255.11 255.255.255.255
bgp 65001
 router-id 10.1.255.11
l2vpn enable
vsi vsi_DEMO
 vxlan 10100
 evpn encapsulation vxlan
  route-distinguisher 65001:10100
  vpn-target 65001:10100 import-extcommunity
interface GE1/0/5
 port link-mode bridge
 service-instance 120
  encapsulation s-vid 120
  xconnect vsi vsi_DEMO
return
"""


def _site(client, auth_headers):
    n = next(_seq)
    return client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": f"Learn DC {n}", "code": f"L-DC{n}", "bgp_asn": 65001},
    ).json()


def test_parse_h3c_inventory():
    inv = config_learn_parse.parse_inventory(H3C_CONFIG, Vendor.H3C)
    assert inv.loopback_ip == "10.1.255.11"
    assert inv.bgp_asn == 65001
    assert len(inv.l2_services) == 1
    svc = inv.l2_services[0]
    assert svc.vni == 10100
    assert svc.rd == "65001:10100"
    assert "GE1/0/5" in svc.interfaces
    assert 120 in inv.vlan_ids


def test_device_learn_api(client, auth_headers):
    site = _site(client, auth_headers)
    n = next(_seq)
    leaf = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"LEARN-H3C-{n}",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "status": "unknown",
            "mgmt_ip": f"10.1.{n}.11",
            "site_id": site["id"],
        },
        params={"learn": False},
    ).json()

    result = client.post(
        f"/api/v1/devices/{leaf['id']}/learn", headers=auth_headers
    ).json()
    assert result["success"] is True, result
    assert result["snapshot_version"] >= 1
    assert result["inventory"]["service_count"] >= 1

    state = client.get(
        f"/api/v1/devices/{leaf['id']}/learned-state", headers=auth_headers
    ).json()
    assert state["has_learned_config"] is True
    assert state["inventory"]["loopback_ip"] == "10.255.255.1"

    drift = client.get(
        f"/api/v1/config/devices/{leaf['id']}/drift", headers=auth_headers
    ).json()
    assert "diff" in drift
    assert drift["learned_version"] >= 1


def test_bulk_import_with_learn(client, auth_headers):
    site = _site(client, auth_headers)
    csv_body = (
        "name,vendor,model,role,overlay_tech,status,mgmt_ip,loopback_ip,bgp_asn,sr_node_sid,site_code\n"
        f"LAB-LEAF-{site['code']},h3c,S6850,leaf,vxlan_evpn,unknown,10.99.0.11,,,,{site['code']}\n"
    )
    resp = client.post(
        "/api/v1/bulk/devices/import?learn=true",
        headers=auth_headers,
        files={"file": ("devices.csv", csv_body, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 1
    assert body["learn_enabled"] is True
    assert body["learn"]["success"] == 1

    devices = client.get("/api/v1/devices", headers=auth_headers).json()
    dev = next(d for d in devices if d["name"] == f"LAB-LEAF-{site['code']}")
    state = client.get(
        f"/api/v1/devices/{dev['id']}/learned-state", headers=auth_headers
    ).json()
    assert state["has_learned_config"] is True


def test_port_inventory_uses_learned_config(client, auth_headers):
    n = next(_seq)
    pe = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"LEARN-CISCO-{n}",
            "vendor": "cisco",
            "role": "pe",
            "overlay_tech": "srmpls_evpn",
            "status": "online",
            "mgmt_ip": f"10.2.{n}.21",
        },
        params={"learn": False},
    ).json()
    client.post(f"/api/v1/devices/{pe['id']}/learn", headers=auth_headers)

    db = SessionLocal()
    try:
        device = db.get(Device, pe["id"])
        usage = port_inventory.device_config_usage(db, device)
        assert "GigabitEthernet0/0/0/1" in usage
        svids = [e.s_vid for e in usage["GigabitEthernet0/0/0/1"].entries]
        assert 100 in svids
    finally:
        db.close()


def test_diff_platform_vs_learned(client, auth_headers):
    site = _site(client, auth_headers)
    leaf = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": "BJ-LEAF-02",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "mgmt_ip": "10.1.0.12",
            "site_id": site["id"],
        },
        params={"learn": False},
    ).json()
    client.post(f"/api/v1/devices/{leaf['id']}/learn", headers=auth_headers)

    db = SessionLocal()
    try:
        device = db.get(Device, leaf["id"])
        diff = config_mgmt.diff_platform_vs_learned(db, device)
        assert "learned-v" in diff or diff == ""
    finally:
        db.close()
