"""Data-plane binding list API fields."""
from __future__ import annotations

import uuid

import pytest

from app.controller import dataplane
from app.models.circuit import Circuit
from app.models.controlplane import DataPlaneBinding
from app.models.device import Device
from app.models.enums import CircuitStatus, DataPlaneState, DeviceRole, DeviceStatus, OverlayTech, ServiceType, Vendor
from app.models.site import Site
from app.models.tenant import Tenant


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def test_list_bindings_includes_circuit_and_device_names(db_session):
    suffix = uuid.uuid4().hex[:8]
    site = Site(name=f"DP Site {suffix}", code=f"DP{suffix[:4]}")
    tenant = Tenant(name=f"DP Tenant {suffix}", code=f"DP-T-{suffix[:4]}")
    db_session.add_all([site, tenant])
    db_session.flush()

    device = Device(
        name=f"pe-{suffix}",
        vendor=Vendor.HUAWEI,
        role=DeviceRole.PE,
        overlay_tech=OverlayTech.VXLAN_EVPN,
        status=DeviceStatus.ONLINE,
        mgmt_ip=f"10.90.{suffix[:2]}.1",
        site_id=site.id,
    )
    circuit = Circuit(
        name=f"line-{suffix}",
        code=f"CIR-{suffix[:6].upper()}",
        tenant_id=tenant.id,
        service_type=ServiceType.L2VPN_EVPN,
        status=CircuitStatus.ACTIVE,
    )
    db_session.add_all([device, circuit])
    db_session.flush()

    db_session.add(
        DataPlaneBinding(
            circuit_id=circuit.id,
            device_id=device.id,
            operation="apply",
            transport="ssh",
            state=DataPlaneState.APPLIED,
        )
    )
    db_session.flush()

    rows = dataplane.list_bindings(db_session)
    match = next(r for r in rows if r["id"] == db_session.query(DataPlaneBinding).one().id)
    assert match["circuit_code"] == circuit.code
    assert match["circuit_name"] == circuit.name
    assert match["device_name"] == device.name
