"""Alarm evaluation must not crash the background scheduler."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.circuit import Circuit
from app.models.enums import CircuitStatus, ServiceType
from app.models.telemetry import TelemetrySample
from app.models.tenant import Tenant
from app.scheduler import run_once
from app.services import alarm_service, telemetry_service


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _circuit(db_session) -> Circuit:
    tenant = Tenant(name="Alarm Tenant", code="ALMT")
    db_session.add(tenant)
    db_session.flush()
    circuit = Circuit(
        name="openai-azure",
        code="CIR-ALM-SVC",
        tenant_id=tenant.id,
        service_type=ServiceType.L2VPN_EVPN,
        status=CircuitStatus.ACTIVE,
        bandwidth_mbps=100,
    )
    db_session.add(circuit)
    db_session.flush()
    return circuit


def test_evaluate_circuit_health_tunnel_down_with_enriched_context(db_session):
    circuit = _circuit(db_session)
    db_session.add(
        TelemetrySample(
            circuit_id=circuit.id,
            rx_mbps=0.0,
            tx_mbps=0.0,
            utilization_pct=0.0,
            latency_ms=0.0,
            tunnel_state="down",
            source="snmp",
            created_at=datetime.now(timezone.utc),
        )
    )
    db_session.flush()
    health = telemetry_service.compute_health(db_session, circuit, hours=24)
    assert health.tunnel_down is True

    alarm_service.evaluate_circuit_health(db_session, circuit, health)
    db_session.flush()

    from app.models.alarm import Alarm
    from app.models.enums import AlarmStatus

    alarm = db_session.query(Alarm).filter(
        Alarm.circuit_id == circuit.id,
        Alarm.kind == "tunnel_down",
        Alarm.status != AlarmStatus.CLEARED,
    ).one()
    assert circuit.code in alarm.title


def test_scheduler_tick_completes(db_session):
    circuit = _circuit(db_session)
    db_session.add(
        TelemetrySample(
            circuit_id=circuit.id,
            rx_mbps=1.0,
            tx_mbps=1.0,
            utilization_pct=1.0,
            tunnel_state="down",
            source="snmp",
            created_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    collected = run_once()
    assert collected >= 0
