"""Tests for IGP cost parsing and weighted underlay path computation."""
from __future__ import annotations

import uuid

import pytest

from app.models.device import Device
from app.models.enums import DeviceRole, DeviceStatus, LinkType, OverlayTech, Vendor
from app.models.link import Link
from app.models.site import Site
from app.services import config_learn_parse, path_service

H3C_IGP_CONFIG = """\
sysname LEAF-A
interface LoopBack0
 ip address 10.1.255.1 255.255.255.255
interface GE1/0/1
 ospf 1 area 0.0.0.0
 ospf cost 100
interface GE1/0/2
 ospf 1 area 0.0.0.0
 ospf cost 10
return
"""

HUAWEI_IGP_CONFIG = """\
sysname PE-A
interface LoopBack0
 ip address 10.2.255.1 255.255.255.255
interface GE1/0/10
 ospf enable 1 area 0.0.0.0
 ospf cost 50
return
"""

CISCO_ISIS_CONFIG = """\
interface GigabitEthernet0/0/0/1
 isis metric 200 level-2
interface GigabitEthernet0/0/0/2
 isis metric 25 level-2
!
"""


def test_parse_h3c_ospf_costs():
    inv = config_learn_parse.parse_inventory(H3C_IGP_CONFIG, Vendor.H3C)
    assert inv.igp_protocol == "ospf"
    costs = {c.interface: c.cost for c in inv.igp_costs}
    assert costs["GE1/0/1"] == 100
    assert costs["GE1/0/2"] == 10


def test_parse_huawei_ospf_costs():
    inv = config_learn_parse.parse_inventory(HUAWEI_IGP_CONFIG, Vendor.HUAWEI)
    assert inv.igp_protocol == "ospf"
    assert len(inv.igp_costs) == 1
    assert inv.igp_costs[0].interface == "GE1/0/10"
    assert inv.igp_costs[0].cost == 50


def test_parse_cisco_isis_costs():
    inv = config_learn_parse.parse_inventory(CISCO_ISIS_CONFIG, Vendor.CISCO)
    assert inv.igp_protocol == "isis"
    costs = {c.interface: c.cost for c in inv.igp_costs}
    assert costs["GigabitEthernet0/0/0/1"] == 200
    assert costs["GigabitEthernet0/0/0/2"] == 25


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _triangle_topology(db):
    suffix = uuid.uuid4().hex[:8]
    site = Site(name=f"IGP Site {suffix}", code=f"IG{suffix}", bgp_asn=65001)
    db.add(site)
    db.flush()

    a = Device(
        name=f"node-a-{suffix}",
        vendor=Vendor.H3C,
        role=DeviceRole.LEAF,
        overlay_tech=OverlayTech.VXLAN_EVPN,
        status=DeviceStatus.ONLINE,
        mgmt_ip=f"10.88.{suffix[:2]}.1",
        loopback_ip=f"10.255.{suffix[:2]}.1",
        site_id=site.id,
    )
    mid = Device(
        name=f"node-m-{suffix}",
        vendor=Vendor.H3C,
        role=DeviceRole.SPINE,
        overlay_tech=OverlayTech.VXLAN_EVPN,
        status=DeviceStatus.ONLINE,
        mgmt_ip=f"10.88.{suffix[2:4]}.2",
        loopback_ip=f"10.255.{suffix[2:4]}.2",
        site_id=site.id,
    )
    z = Device(
        name=f"node-z-{suffix}",
        vendor=Vendor.H3C,
        role=DeviceRole.LEAF,
        overlay_tech=OverlayTech.VXLAN_EVPN,
        status=DeviceStatus.ONLINE,
        mgmt_ip=f"10.88.{suffix[4:6]}.3",
        loopback_ip=f"10.255.{suffix[4:6]}.3",
        site_id=site.id,
    )
    db.add_all([a, mid, z])
    db.flush()

    db.add_all([
        Link(
            name=f"A-M-{suffix}",
            type=LinkType.INTRA_DC,
            device_a_id=a.id,
            device_z_id=mid.id,
            interface_a="GE1/0/1",
            interface_z="GE1/0/1",
            capacity_mbps=10000,
        ),
        Link(
            name=f"M-Z-{suffix}",
            type=LinkType.INTRA_DC,
            device_a_id=mid.id,
            device_z_id=z.id,
            interface_a="GE1/0/2",
            interface_z="GE1/0/1",
            capacity_mbps=10000,
        ),
        Link(
            name=f"A-Z-{suffix}",
            type=LinkType.DCI,
            device_a_id=a.id,
            device_z_id=z.id,
            interface_a="GE1/0/2",
            interface_z="GE1/0/2",
            capacity_mbps=10000,
        ),
    ])
    db.flush()

    from app.models.device_learn_run import DeviceLearnRun

    for dev, iface_costs in [
        (a, {"GE1/0/1": 100, "GE1/0/2": 5}),
        (mid, {"GE1/0/1": 10, "GE1/0/2": 10}),
        (z, {"GE1/0/1": 10, "GE1/0/2": 10}),
    ]:
        db.add(DeviceLearnRun(
            device_id=dev.id,
            status="success",
            inventory={
                "igp_protocol": "ospf",
                "igp_costs": [
                    {"interface": iface, "cost": cost, "protocol": "ospf"}
                    for iface, cost in iface_costs.items()
                ],
            },
        ))
    db.commit()
    return a, mid, z


def test_weighted_path_prefers_lower_cost(db_session):
    a, _mid, z = _triangle_topology(db_session)
    path, total, algo = path_service.shortest_path_weighted(db_session, a.id, z.id)
    assert algo == "dijkstra_igp_cost"
    assert path == [a.id, z.id]
    assert total == 5.0


def test_weighted_path_via_spine_when_direct_expensive(db_session):
    a, mid, z = _triangle_topology(db_session)
    from sqlalchemy import select
    from app.models.device_learn_run import DeviceLearnRun

    direct = db_session.execute(
        select(Link).where(Link.device_a_id == a.id, Link.device_z_id == z.id)
    ).scalar_one()
    direct.interface_a = "GE1/0/99"
    db_session.flush()

    run = db_session.execute(
        select(DeviceLearnRun)
        .where(DeviceLearnRun.device_id == a.id, DeviceLearnRun.status == "success")
        .order_by(DeviceLearnRun.id.desc())
    ).scalar_one()
    inv = dict(run.inventory or {})
    costs = list(inv.get("igp_costs") or [])
    costs.append({"interface": "GE1/0/99", "cost": 500, "protocol": "ospf"})
    inv["igp_costs"] = costs
    run.inventory = inv
    db_session.commit()

    path, total, _ = path_service.shortest_path_weighted(db_session, a.id, z.id)
    assert path == [a.id, mid.id, z.id]
    assert total == 110.0
