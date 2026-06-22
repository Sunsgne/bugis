"""Tests for background circuit deletion."""
from __future__ import annotations

import itertools

from app.core.database import SessionLocal
from app.models.circuit import Circuit, CircuitEndpoint
from app.models.enums import CircuitStatus, ServiceType
from app.models.tenant import Tenant
from app.services import circuit_delete_service

_seq = itertools.count(1)


def test_delete_circuit_record_removes_row():
    db = SessionLocal()
    try:
        n = next(_seq)
        tenant = Tenant(name=f"T-{n}", code=f"TEN{n}", type="enterprise")
        db.add(tenant)
        db.flush()
        circuit = Circuit(
            code=f"CIR-{n}",
            name="delete-me",
            tenant_id=tenant.id,
            service_type=ServiceType.L2VPN_EVPN,
            status=CircuitStatus.DECOMMISSIONED,
            bandwidth_mbps=100,
        )
        db.add(circuit)
        db.flush()
        db.add(
            CircuitEndpoint(
                circuit_id=circuit.id,
                device_id=1,
                label="A",
                interface_name="GE1/0/1",
            )
        )
        db.commit()
        circuit_id = circuit.id

        result = circuit_delete_service.delete_circuit_by_id(db, circuit_id)
        db.commit()

        assert result["circuit_id"] == circuit_id
        assert db.get(Circuit, circuit_id) is None
    finally:
        db.close()
