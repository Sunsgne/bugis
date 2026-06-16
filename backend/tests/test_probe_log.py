"""Probe log persistence tests."""
from __future__ import annotations

import pytest

from app.models.circuit import Circuit, CircuitEndpoint
from app.models.enums import CircuitStatus, ServiceType, Vendor
from app.models.tenant import Tenant
from app.models.device import Device
from app.services import probe_log_service


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def test_save_and_load_probe_log(db_session):
    tenant = Tenant(name="T", code="T01")
    db_session.add(tenant)
    db_session.flush()
    dev = Device(name="d1", vendor=Vendor.H3C, mgmt_ip="10.0.0.1")
    db_session.add(dev)
    db_session.flush()
    circuit = Circuit(
        name="C1", code="C-001", tenant_id=tenant.id,
        service_type=ServiceType.L2VPN_EVPN, status=CircuitStatus.ACTIVE,
        bandwidth_mbps=100,
    )
    db_session.add(circuit)
    db_session.flush()
    db_session.add(CircuitEndpoint(circuit_id=circuit.id, device_id=dev.id, label="A", interface_name="GE1/0/1"))
    db_session.commit()

    result = {"mode": "live", "probe_method": "fabric_loopback", "reachable": True, "rtt_ms": 3.0}
    row = probe_log_service.save_probe_log(db_session, circuit, result)
    db_session.commit()

    latest = probe_log_service.latest_probe_log(db_session, circuit.id)
    assert latest is not None
    assert latest.id == row.id
    assert latest.result_json["rtt_ms"] == 3.0
