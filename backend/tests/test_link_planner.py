"""Tests for backbone link planning."""
from __future__ import annotations

import itertools

from app.core.database import SessionLocal
from app.models.device import Device, DeviceInterface
from app.models.enums import DeviceRole, LinkType, Vendor
from app.models.link import Link
from app.models.site import Site
from app.services import link_planner

_seq = itertools.count(1)


def _site(db, code: str) -> Site:
    site = Site(name=code, code=code, bgp_asn=65000)
    db.add(site)
    db.flush()
    return site


def _device(db, site: Site, name: str, role: DeviceRole) -> Device:
    device = Device(
        name=name,
        vendor=Vendor.H3C,
        role=role,
        mgmt_ip=f"10.{next(_seq)}.0.1",
        site_id=site.id,
    )
    db.add(device)
    db.flush()
    return device


def _iface(db, device: Device, name: str, speed: int, desc: str, oper: str = "up") -> None:
    db.add(
        DeviceInterface(
            device_id=device.id,
            name=name,
            speed_mbps=speed,
            description=desc,
            oper_status=oper,
            discovered_via="snmp",
        )
    )


def test_plan_link_prefers_uplink_ports():
    db = SessionLocal()
    try:
        site_a = _site(db, "SIN")
        site_z = _site(db, "HKG")
        dev_a = _device(db, site_a, "leaf-a", DeviceRole.LEAF)
        dev_z = _device(db, site_z, "leaf-z", DeviceRole.LEAF)
        _iface(db, dev_a, "Twenty-FiveGigE1/0/1", 25000, "SVR customer", "up")
        _iface(db, dev_a, "HundredGigE1/0/30", 100000, "uplink to HKG DCI", "up")
        _iface(db, dev_z, "Twenty-FiveGigE1/0/2", 25000, "access", "up")
        _iface(db, dev_z, "HundredGigE1/0/30", 100000, "backbone peer", "up")
        db.commit()

        plan = link_planner.plan_link(db, dev_a, dev_z)
        assert plan is not None
        assert plan["interface_a"] == "HundredGigE1/0/30"
        assert plan["interface_z"] == "HundredGigE1/0/30"
        assert plan["type"] == LinkType.DCI.value
        assert plan["capacity_mbps"] == 100000
    finally:
        db.close()


def test_suggest_skips_existing_pairs():
    db = SessionLocal()
    try:
        site_a = _site(db, "A")
        site_z = _site(db, "Z")
        dev_a = _device(db, site_a, "a1", DeviceRole.DCI_GW)
        dev_z = _device(db, site_z, "z1", DeviceRole.DCI_GW)
        _iface(db, dev_a, "HundredGigE1/0/1", 100000, "uplink", "up")
        _iface(db, dev_z, "HundredGigE1/0/1", 100000, "uplink", "up")
        db.add(
            Link(
                name="existing",
                type=LinkType.DCI,
                device_a_id=dev_a.id,
                device_z_id=dev_z.id,
                interface_a="HundredGigE1/0/1",
                interface_z="HundredGigE1/0/1",
                capacity_mbps=100000,
            )
        )
        db.commit()

        suggestions = link_planner.suggest_backbone_links(db)
        pair = (min(dev_a.id, dev_z.id), max(dev_a.id, dev_z.id))
        suggested_pairs = {
            (min(s["device_a_id"], s["device_z_id"]), max(s["device_a_id"], s["device_z_id"]))
            for s in suggestions
        }
        assert pair not in suggested_pairs
    finally:
        db.close()


def test_link_suggestions_api(client, auth_headers):
    n = next(_seq)
    site_a = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": f"DC-A-{n}", "code": f"DCA{n}", "bgp_asn": 65001},
    ).json()
    site_z = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": f"DC-Z-{n}", "code": f"DCZ{n}", "bgp_asn": 65001},
    ).json()
    dev_a = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"GW-A-{n}",
            "vendor": "h3c",
            "role": "dci_gw",
            "mgmt_ip": f"10.8.{n}.1",
            "site_id": site_a["id"],
        },
        params={"learn": False},
    ).json()
    dev_z = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"GW-Z-{n}",
            "vendor": "h3c",
            "role": "dci_gw",
            "mgmt_ip": f"10.8.{n}.2",
            "site_id": site_z["id"],
        },
        params={"learn": False},
    ).json()
    client.post(f"/api/v1/devices/{dev_a['id']}/discover-interfaces", headers=auth_headers)
    client.post(f"/api/v1/devices/{dev_z['id']}/discover-interfaces", headers=auth_headers)

    suggestions = client.get("/api/v1/capacity/links/suggestions", headers=auth_headers).json()
    pair = {dev_a["id"], dev_z["id"]}
    row = next(
        s for s in suggestions
        if {s["device_a_id"], s["device_z_id"]} == pair
    )
    assert row["interface_a"]
    assert row["interface_z"]

    created = client.post(
        "/api/v1/capacity/links/bulk",
        headers=auth_headers,
        json={"links": [row]},
    ).json()
    assert len(created) == 1
    usage = client.get("/api/v1/capacity/links/usage", headers=auth_headers).json()
    assert any(u["name"] == row["name"] for u in usage)
