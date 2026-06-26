"""Data-plane binding deduplication when a circuit has multiple ports on one device."""
from __future__ import annotations

import uuid

from app.controller import dataplane
from app.core.database import SessionLocal
from app.models.circuit import Circuit, CircuitEndpoint
from app.models.controlplane import DataPlaneBinding
from app.models.device import Device
from app.models.enums import CircuitStatus, OverlayTech, ServiceType, Vendor
from app.models.tenant import Tenant


def _device(db, suffix: str) -> Device:
    device = Device(
        name=f"pe-dual-{suffix}",
        vendor=Vendor.H3C,
        mgmt_ip="10.0.0.24",
        loopback_ip="10.1.0.24",
        overlay_tech=OverlayTech.VXLAN_EVPN,
    )
    db.add(device)
    db.flush()
    return device


def test_plan_bindings_dedupes_same_device_endpoints():
    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        tenant = Tenant(name=f"Dual Port {suffix}", code=f"DP{suffix}")
        db.add(tenant)
        db.flush()
        pe = _device(db, suffix)
        circuit = Circuit(
            code=f"CIR-DUAL-{suffix}",
            name="dual-homed access",
            tenant_id=tenant.id,
            service_type=ServiceType.L2VPN_EVPN,
            status=CircuitStatus.PROVISIONING,
            vni=30100,
            route_target="65000:30100",
        )
        db.add(circuit)
        db.flush()
        endpoints = [
            CircuitEndpoint(
                circuit_id=circuit.id,
                device_id=pe.id,
                label="C",
                interface_name="GE1/0/1",
                vlan_id=100,
            ),
            CircuitEndpoint(
                circuit_id=circuit.id,
                device_id=pe.id,
                label="D",
                interface_name="GE1/0/2",
                vlan_id=100,
            ),
        ]
        for ep in endpoints:
            ep.device = pe
            db.add(ep)
        db.flush()

        bindings = dataplane.plan_bindings(db, circuit, endpoints, "apply")
        assert len(bindings) == 1

        # Retry after a failed provision should not raise MultipleResultsFound.
        bindings_again = dataplane.plan_bindings(db, circuit, endpoints, "apply")
        assert len(bindings_again) == 1
        assert (
            db.query(DataPlaneBinding)
            .filter(
                DataPlaneBinding.circuit_id == circuit.id,
                DataPlaneBinding.device_id == pe.id,
                DataPlaneBinding.operation == "apply",
            )
            .count()
            == 1
        )
    finally:
        db.rollback()
        db.close()
