"""BGP EVPN session helpers."""
from __future__ import annotations

import uuid

import pytest

from app.controller import bgp_peering
from app.models.device import Device
from app.models.enums import DeviceRole, DeviceStatus, OverlayTech, Vendor
from app.models.site import Site


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _device(db_session) -> Device:
    suffix = uuid.uuid4().hex[:8]
    site = Site(name=f"Site {suffix}", code=f"S{suffix}", bgp_asn=65001)
    db_session.add(site)
    db_session.flush()
    dev = Device(
        name=f"dev-{suffix}",
        vendor=Vendor.H3C,
        role=DeviceRole.DCI_GW,
        overlay_tech=OverlayTech.VXLAN_EVPN,
        status=DeviceStatus.ONLINE,
        mgmt_ip=f"10.88.{suffix[:2]}.1",
        loopback_ip=f"10.88.{suffix[2:4]}.1",
        bgp_asn=65001,
        site_id=site.id,
    )
    db_session.add(dev)
    db_session.flush()
    return dev


def test_ensure_sessions_dedupes_duplicate_devices(db_session):
    device = _device(db_session)
    sessions = bgp_peering.ensure_sessions(db_session, [device, device, device])
    assert len(sessions) == 1
    assert sessions[0].device_id == device.id

    again = bgp_peering.ensure_sessions(db_session, [device])
    assert len(again) == 1
    assert again[0].id == sessions[0].id
