"""Tests for VNI-centric circuit adoption from whole-network learned config."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.models.device import Device, DeviceInterface
from app.models.enums import DeviceRole, Vendor
from app.models.site import Site
from app.services import circuit_adopt, config_mgmt

_seq = itertools.count(1)

H3C_VNI_1666_CONFIG = """\
sysname leaf-a
l2vpn enable
vsi sdwan-bb
 vxlan 1666
 evpn encapsulation vxlan
  route-distinguisher 65001:1666
  vpn-target 65001:1666 import-extcommunity
  vpn-target 65001:1666 export-extcommunity
interface Twenty-FiveGigE1/0/51
 port link-mode bridge
 service-instance 1666
  encapsulation s-vid 1666
  xconnect vsi sdwan-bb
return
"""

HUAWEI_VNI_1666_CONFIG = """\
sysname leaf-z
bridge-domain 1666
 vxlan vni 1666
interface GE1/0/10.1666
 mode l2
 encapsulation dot1q vid 1666
 bridge-domain 1666
return
"""


def _site(db) -> Site:
    n = next(_seq)
    site = Site(name=f"DC-{n}", code=f"DC{n}", bgp_asn=65001)
    db.add(site)
    db.flush()
    return site


def _device(db, site: Site, name: str) -> Device:
    n = next(_seq)
    device = Device(
        name=name,
        vendor=Vendor.H3C,
        role=DeviceRole.LEAF,
        mgmt_ip=f"10.40.{n}.1",
        site_id=site.id,
    )
    db.add(device)
    db.flush()
    return device


def _learn(db, device: Device, content: str) -> None:
    config_mgmt.add_snapshot(
        db,
        device,
        content,
        source="learn",
        note="test",
        created_by="test",
    )


def test_binding_matches_vni_when_binding_vni_missing():
    inventory = {
        "l2_services": [{"name": "sdwan-bb", "vni": 1666, "interfaces": ["GE1/0/1"]}],
        "access_bindings": [{
            "interface": "GE1/0/1",
            "access_mode": "dot1q",
            "s_vid": 1666,
            "vsi_name": "sdwan-bb",
        }],
    }
    raw = inventory["access_bindings"][0]
    assert circuit_adopt._binding_matches_vni(raw, 1666, inventory)


def test_find_adoptable_endpoints_resolves_cli_interface_alias():
    db = SessionLocal()
    try:
        site = _site(db)
        dev = _device(db, site, "h3c-a")
        db.add(
            DeviceInterface(
                device_id=dev.id,
                name="25G-1/0/51",
                discovered_via="snmp",
                ifindex=51,
                used_s_vids=[
                    {
                        "s_vid": 1666,
                        "access_mode": "dot1q",
                        "source": "device",
                        "vsi_name": "sdwan-bb",
                    }
                ],
            )
        )
        _learn(db, dev, H3C_VNI_1666_CONFIG)
        db.commit()

        endpoints = circuit_adopt.find_adoptable_endpoints_by_vni(db, 1666)
        assert len(endpoints) == 1
        assert endpoints[0]["adoptable"] is True
        assert endpoints[0]["interface_name"] == "25G-1/0/51"
        assert endpoints[0]["vlan_id"] == 1666
    finally:
        db.close()


def test_find_adoptable_endpoints_skips_huawei_physical_interface():
    db = SessionLocal()
    try:
        site = _site(db)
        dev = _device(db, site, "hw-phys")
        dev.vendor = Vendor.HUAWEI
        _learn(
            db,
            dev,
            """\
interface GE1/0/10
 encapsulation dot1q vid 1666
 bridge-domain 1666
""",
        )
        db.commit()
        endpoints = [
            row
            for row in circuit_adopt.find_adoptable_endpoints_by_vni(db, 1666)
            if row["device_id"] == dev.id
        ]
        assert endpoints == []
    finally:
        db.rollback()
        db.close()


def test_find_adoptable_endpoints_skips_h3c_without_service_instance():
    db = SessionLocal()
    try:
        site = _site(db)
        dev = _device(db, site, "h3c-legacy")
        _learn(
            db,
            dev,
            """\
vsi sdwan-bb
 vxlan 1666
interface Twenty-FiveGigE1/0/51
 xconnect vsi sdwan-bb
""",
        )
        db.commit()
        endpoints = [
            row
            for row in circuit_adopt.find_adoptable_endpoints_by_vni(db, 1666)
            if row["device_id"] == dev.id
        ]
        assert endpoints == []
    finally:
        db.rollback()
        db.close()


def test_find_adoptable_endpoints_discovers_huawei_bridge_domain_vni():
    db = SessionLocal()
    try:
        site = _site(db)
        dev = _device(db, site, "hw-z")
        dev.vendor = Vendor.HUAWEI
        db.add(
            DeviceInterface(
                device_id=dev.id,
                name="GE1/0/10.1666",
                discovered_via="snmp",
                ifindex=10,
                used_s_vids=[
                    {
                        "s_vid": 1666,
                        "access_mode": "dot1q",
                        "source": "device",
                    }
                ],
            )
        )
        _learn(db, dev, HUAWEI_VNI_1666_CONFIG)
        db.commit()

        endpoints = circuit_adopt.find_adoptable_endpoints_by_vni(db, 1666)
        device_rows = [row for row in endpoints if row["device_id"] == dev.id]
        assert len(device_rows) == 1
        assert device_rows[0]["adoptable"] is True
    finally:
        db.close()


def test_find_adoptable_endpoints_across_two_devices():
    db = SessionLocal()
    try:
        site_a = _site(db)
        site_z = _site(db)
        dev_a = _device(db, site_a, "h3c-a2")
        dev_z = _device(db, site_z, "hw-z2")
        dev_z.vendor = Vendor.HUAWEI
        db.add(
            DeviceInterface(
                device_id=dev_a.id,
                name="25G-1/0/51",
                discovered_via="snmp",
                ifindex=51,
                used_s_vids=[
                    {"s_vid": 1666, "access_mode": "dot1q", "source": "device", "vsi_name": "sdwan-bb"}
                ],
            )
        )
        db.add(
            DeviceInterface(
                device_id=dev_z.id,
                name="GE1/0/10.1666",
                discovered_via="snmp",
                ifindex=10,
                used_s_vids=[
                    {"s_vid": 1666, "access_mode": "dot1q", "source": "device"}
                ],
            )
        )
        _learn(db, dev_a, H3C_VNI_1666_CONFIG)
        _learn(db, dev_z, HUAWEI_VNI_1666_CONFIG)
        db.commit()

        endpoints = circuit_adopt.find_adoptable_endpoints_by_vni(db, 1666)
        adoptable = [
            row for row in endpoints
            if row["adoptable"] and row["device_id"] in {dev_a.id, dev_z.id}
        ]
        assert len(adoptable) == 2
        assert {row["device_id"] for row in adoptable} == {dev_a.id, dev_z.id}
    finally:
        db.close()


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
