"""Telemetry sample windowing and health scoping."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.circuit import Circuit
from app.models.enums import CircuitStatus, ServiceType
from app.models.telemetry import TelemetrySample
from app.models.tenant import Tenant
from app.services import telemetry_service


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def test_list_circuit_samples_returns_most_recent_within_limit(db_session):
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(name=f"T {suffix}", code=f"T{suffix}")
    db_session.add(tenant)
    db_session.flush()
    circuit = Circuit(
        name="Window Circuit",
        code=f"WIN-{suffix}",
        tenant_id=tenant.id,
        service_type=ServiceType.L2VPN_EVPN,
        status=CircuitStatus.ACTIVE,
        bandwidth_mbps=100,
    )
    db_session.add(circuit)
    db_session.flush()

    base = datetime.now(timezone.utc) - timedelta(hours=10)
    for i in range(10):
        db_session.add(
            TelemetrySample(
                circuit_id=circuit.id,
                rx_mbps=float(i),
                tx_mbps=float(i),
                latency_ms=1.0,
                jitter_ms=0.1,
                packet_loss_pct=0.0,
                utilization_pct=float(i),
                tunnel_state="up",
                source="snmp",
                created_at=base + timedelta(hours=i),
            )
        )
    db_session.commit()

    rows = telemetry_service.list_circuit_samples(
        db_session, circuit.id, hours=24, limit=3
    )
    assert len(rows) == 3
    assert [s.rx_mbps for s in rows] == [7.0, 8.0, 9.0]

    health = telemetry_service.compute_health(
        db_session, circuit, limit=3, hours=24
    )
    assert health.samples == 3
    assert health.avg_utilization_pct == 8.0
