"""Tests for overlay VNI/VSI inventory and smart allocation."""
from __future__ import annotations

import itertools

from app.core.database import SessionLocal
from app.models.device import Device
from app.models.device_learn_run import DeviceLearnRun
from app.models.enums import Vendor
from app.services import allocation, config_learn_parse, overlay_inventory

_seq = itertools.count(1)

H3C_OVERLAY_CONFIG = """\
sysname LEAF-01
l2vpn enable
vsi cus-live-001
 vxlan 10148
 evpn encapsulation vxlan
  route-distinguisher 10.1.1.1:10148
  vpn-target 65001:10148 import-extcommunity
  vpn-target 65001:10148 export-extcommunity
interface GE1/0/2
 port link-mode bridge
 service-instance 2302
  encapsulation s-vid 2302
  xconnect vsi cus-live-001
return
"""


def test_parse_h3c_overlay_services():
    inv = config_learn_parse.parse_inventory(H3C_OVERLAY_CONFIG, Vendor.H3C)
    assert len(inv.l2_services) == 1
    svc = inv.l2_services[0]
    assert svc.name == "cus-live-001"
    assert svc.vni == 10148


def test_overlay_inventory_marks_network_services():
    db = SessionLocal()
    try:
        device = Device(name="OVL-LEAF", vendor=Vendor.H3C, mgmt_ip="10.9.0.1")
        db.add(device)
        db.flush()
        inv = config_learn_parse.parse_inventory(H3C_OVERLAY_CONFIG, Vendor.H3C)
        db.add(
            DeviceLearnRun(
                device_id=device.id,
                status="success",
                inventory=inv.as_dict(),
            )
        )
        db.commit()

        result = overlay_inventory.device_overlay_inventory(db, device)
        assert result["service_count"] == 1
        assert result["network_only_count"] == 1
        assert result["vnis"] == [10148]
        assert result["items"][0]["source"] == "network"
    finally:
        db.close()


def test_allocate_vni_skips_network_vni(monkeypatch):
    db = SessionLocal()
    try:
        device = Device(name="OVL-LEAF-2", vendor=Vendor.H3C, mgmt_ip="10.9.0.2")
        db.add(device)
        db.flush()
        inv = config_learn_parse.parse_inventory(H3C_OVERLAY_CONFIG, Vendor.H3C)
        db.add(
            DeviceLearnRun(
                device_id=device.id,
                status="success",
                inventory=inv.as_dict(),
            )
        )
        db.commit()

        monkeypatch.setattr(
            "app.core.config.settings.smart_overlay_allocation",
            True,
        )
        vni = allocation.allocate_vni(db)
        assert vni != 10148
        assert vni >= allocation.VNI_BASE
    finally:
        db.close()


def test_overlay_inventory_api(client, auth_headers):
    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": "OVL DC", "code": f"OVL{next(_seq)}", "bgp_asn": 65001},
    ).json()
    n = next(_seq)
    device = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"OVL-DEV-{n}",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "mgmt_ip": f"10.8.{n}.1",
            "site_id": site["id"],
        },
        params={"learn": False},
    ).json()
    client.post(f"/api/v1/devices/{device['id']}/learn", headers=auth_headers)

    per_dev = client.get(
        f"/api/v1/devices/{device['id']}/overlay-inventory",
        headers=auth_headers,
    )
    assert per_dev.status_code == 200

    fleet = client.get("/api/v1/controller/overlay-inventory", headers=auth_headers)
    assert fleet.status_code == 200
    body = fleet.json()
    assert body["devices_scanned"] >= 1
    assert "reserved_vnis" in body

    scan = client.post(
        "/api/v1/controller/overlay-inventory/scan",
        headers=auth_headers,
    )
    assert scan.status_code == 200
