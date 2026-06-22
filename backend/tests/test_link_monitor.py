"""Backbone link utilization must reflect current contract bandwidth."""
from __future__ import annotations

import uuid

import pytest

from app.models.device import Device, DeviceInterface
from app.models.enums import DeviceRole, DeviceStatus, LinkType, OverlayTech, Vendor
from app.models.link import Link
from app.models.site import Site
from app.models.telemetry import TelemetrySample
from app.services import link_monitor


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _seed_link(db_session) -> tuple[Link, Device, Device]:
    suffix = uuid.uuid4().hex[:8]
    site_a = Site(name=f"Site A {suffix}", code=f"SA{suffix}", bgp_asn=65001)
    site_z = Site(name=f"Site Z {suffix}", code=f"SZ{suffix}", bgp_asn=65002)
    db_session.add_all([site_a, site_z])
    db_session.flush()

    dev_a = Device(
        name=f"dev-a-{suffix}",
        vendor=Vendor.H3C,
        role=DeviceRole.DCI_GW,
        overlay_tech=OverlayTech.VXLAN_EVPN,
        status=DeviceStatus.ONLINE,
        mgmt_ip=f"10.99.{suffix[:2]}.1",
        site_id=site_a.id,
    )
    dev_z = Device(
        name=f"dev-z-{suffix}",
        vendor=Vendor.HUAWEI,
        role=DeviceRole.DCI_GW,
        overlay_tech=OverlayTech.VXLAN_EVPN,
        status=DeviceStatus.ONLINE,
        mgmt_ip=f"10.99.{suffix[2:4]}.2",
        site_id=site_z.id,
    )
    db_session.add_all([dev_a, dev_z])
    db_session.flush()

    iface_a = "Vlan-interface2600"
    iface_z = "Vlanif2600"
    db_session.add_all(
        [
            DeviceInterface(device_id=dev_a.id, name=iface_a, speed_mbps=10000),
            DeviceInterface(device_id=dev_z.id, name=iface_z, speed_mbps=10000),
        ]
    )

    link = Link(
        name=f"DCI-{suffix}",
        type=LinkType.DCI,
        device_a_id=dev_a.id,
        device_z_id=dev_z.id,
        interface_a=iface_a,
        interface_z=iface_z,
        capacity_mbps=1000,
    )
    db_session.add(link)
    db_session.flush()

    db_session.add(
        TelemetrySample(
            device_id=dev_a.id,
            interface_name=iface_a,
            rx_mbps=780.0,
            tx_mbps=120.0,
            utilization_pct=78.0,
            tunnel_state="up",
            source="snmp-link",
        )
    )
    db_session.commit()
    return link, dev_a, dev_z


def test_compute_link_health_recalculates_after_capacity_sync(db_session):
    link, _, _ = _seed_link(db_session)

    stale = link_monitor.compute_link_health(db_session, link)
    assert stale.peak_utilization_pct == 78.0

    link.capacity_mbps = 10000
    db_session.commit()

    fresh = link_monitor.compute_link_health(db_session, link)
    assert fresh.peak_utilization_pct == 7.8
    assert fresh.peak_rx_mbps == 780.0
    assert fresh.peak_tx_mbps == 120.0


def test_sample_utilization_uses_peak_direction(db_session):
    link, dev_a, _ = _seed_link(db_session)
    sample = link_monitor._recent_interface_samples(db_session, dev_a.id, link.interface_a, 1)[0]
    assert link_monitor._sample_utilization_pct(sample, 10000) == 7.8
    assert link_monitor._sample_utilization_pct(sample, 1000) == 78.0


def test_compute_link_health_matches_vlanif_alias(db_session):
    """Samples stored under Vlanif* must match link configured as Vlan-interface*."""
    suffix = uuid.uuid4().hex[:8]
    site_a = Site(name=f"Site A2 {suffix}", code=f"SA2{suffix}", bgp_asn=65001)
    site_z = Site(name=f"Site Z2 {suffix}", code=f"SZ2{suffix}", bgp_asn=65002)
    db_session.add_all([site_a, site_z])
    db_session.flush()

    dev_a = Device(
        name=f"dev-a2-{suffix}",
        vendor=Vendor.H3C,
        role=DeviceRole.DCI_GW,
        overlay_tech=OverlayTech.VXLAN_EVPN,
        status=DeviceStatus.ONLINE,
        mgmt_ip=f"10.98.{suffix[:2]}.1",
        site_id=site_a.id,
    )
    dev_z = Device(
        name=f"dev-z2-{suffix}",
        vendor=Vendor.HUAWEI,
        role=DeviceRole.DCI_GW,
        overlay_tech=OverlayTech.VXLAN_EVPN,
        status=DeviceStatus.ONLINE,
        mgmt_ip=f"10.98.{suffix[2:4]}.2",
        site_id=site_z.id,
    )
    db_session.add_all([dev_a, dev_z])
    db_session.flush()

    iface_a = "Vlan-interface3006"
    iface_z = "Vlanif3006"
    db_session.add_all([
        DeviceInterface(device_id=dev_a.id, name=iface_a, ifindex=3006, speed_mbps=10000),
        DeviceInterface(device_id=dev_z.id, name=iface_z, ifindex=3006, speed_mbps=10000),
    ])

    link = Link(
        name=f"DCI-alias-{suffix}",
        type=LinkType.DCI,
        device_a_id=dev_a.id,
        device_z_id=dev_z.id,
        interface_a=iface_a,
        interface_z=iface_z,
        capacity_mbps=1000,
    )
    db_session.add(link)
    db_session.flush()

    db_session.add(
        TelemetrySample(
            device_id=dev_z.id,
            interface_name=iface_z,
            rx_mbps=45.0,
            tx_mbps=12.0,
            utilization_pct=4.5,
            tunnel_state="up",
            source="snmp-link",
        )
    )
    db_session.commit()

    health = link_monitor.compute_link_health(db_session, link)
    assert health.samples == 1
    assert health.peak_utilization_pct == 4.5
