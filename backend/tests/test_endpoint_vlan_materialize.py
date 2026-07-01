"""Endpoint VLAN materialization from circuit-level allocation."""
from __future__ import annotations

import uuid

from app.core.database import SessionLocal
from app.models.circuit import Circuit, CircuitEndpoint
from app.models.device import Device
from app.models.enums import AccessMode, CircuitStatus, ServiceType, Vendor
from app.models.tenant import Tenant
from app.services import allocation


def test_materialize_endpoint_vlans_copies_circuit_vlan():
    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        tenant = Tenant(name=f"VLAN {suffix}", code=f"V{suffix}")
        device = Device(name=f"PE-{suffix}", vendor=Vendor.H3C, mgmt_ip="10.0.0.1")
        db.add_all([tenant, device])
        db.flush()
        circuit = Circuit(
            name="VLAN Circuit",
            code=f"VL-{suffix}",
            tenant_id=tenant.id,
            service_type=ServiceType.L2VPN_EVPN,
            status=CircuitStatus.DRAFT,
            vlan_id=1200,
        )
        db.add(circuit)
        db.flush()
        ep = CircuitEndpoint(
            circuit_id=circuit.id,
            device_id=device.id,
            label="A",
            interface_name="GE1/0/1",
            access_mode=AccessMode.DOT1Q,
        )
        db.add(ep)
        db.flush()
        allocation.materialize_endpoint_vlans(circuit)
        assert ep.vlan_id == 1200
    finally:
        db.rollback()
        db.close()
