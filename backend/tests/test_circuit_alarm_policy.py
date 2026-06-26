"""Alarm grace period and per-kind enablement for circuits."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.circuit import Circuit
from app.models.enums import CircuitStatus, ServiceType
from app.models.platform_settings import PlatformSettings
from app.models.tenant import Tenant
from app.schemas.telemetry import CircuitHealth
from app.services import alarm_service
from app.services.circuit_alarm_settings import (
    alarms_suppressed,
    parse_enabled_alarm_kinds,
    serialize_enabled_alarm_kinds,
)


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def platform_row(db_session) -> PlatformSettings:
    row = db_session.get(PlatformSettings, 1)
    if row:
        return row
    row = PlatformSettings(id=1)
    db_session.add(row)
    db_session.flush()
    return row


def _circuit(db_session, **overrides) -> Circuit:
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(name=f"Grace {suffix}", code=f"G{suffix}")
    db_session.add(tenant)
    db_session.flush()
    circuit = Circuit(
        name="Grace Circuit",
        code=f"GR-{suffix}",
        tenant_id=tenant.id,
        service_type=ServiceType.L2VPN_EVPN,
        status=CircuitStatus.ACTIVE,
        bandwidth_mbps=100,
    )
    for key, value in overrides.items():
        setattr(circuit, key, value)
    db_session.add(circuit)
    db_session.commit()
    db_session.refresh(circuit)
    return circuit


def _health(circuit: Circuit, **updates) -> CircuitHealth:
    base = dict(
        circuit_id=circuit.id,
        circuit_code=circuit.code,
        status="active",
        avg_latency_ms=1.0,
        avg_jitter_ms=0.0,
        avg_packet_loss_pct=0.0,
        avg_utilization_pct=1.0,
        peak_utilization_pct=99.0,
        bandwidth_mbps=100,
        samples=2,
        qos_samples=1,
        health_score=10.0,
        tunnel_down=False,
    )
    base.update(updates)
    return CircuitHealth(**base)


def test_alarms_suppressed_within_grace_window(db_session):
    now = datetime.now(timezone.utc)
    circuit = _circuit(
        db_session,
        activated_at=now,
        alarm_suppress_minutes=60,
    )
    assert alarms_suppressed(circuit) is True


def test_alarms_not_suppressed_after_grace_window(db_session):
    circuit = _circuit(
        db_session,
        activated_at=datetime.now(timezone.utc) - timedelta(hours=2),
        alarm_suppress_minutes=60,
    )
    assert alarms_suppressed(circuit) is False


def test_evaluate_skips_alarms_during_grace(db_session, platform_row):
    circuit = _circuit(
        db_session,
        activated_at=datetime.now(timezone.utc),
        alarm_suppress_minutes=60,
        enabled_alarm_kinds=serialize_enabled_alarm_kinds(["utilization"]),
    )
    health = _health(circuit)
    alarm_service.evaluate_circuit_health(db_session, circuit, health)
    db_session.commit()
    from app.models.alarm import Alarm

    rows = db_session.query(Alarm).filter(Alarm.circuit_id == circuit.id).all()
    assert rows == []


def test_disabled_alarm_kind_does_not_raise(db_session, platform_row):
    circuit = _circuit(
        db_session,
        enabled_alarm_kinds=serialize_enabled_alarm_kinds(["tunnel_down"]),
    )
    health = _health(circuit)
    alarm_service.evaluate_circuit_health(db_session, circuit, health)
    db_session.commit()
    from app.models.alarm import Alarm

    kinds = {a.kind for a in db_session.query(Alarm).filter(Alarm.circuit_id == circuit.id)}
    assert "utilization" not in kinds
    assert "health" not in kinds


def test_parse_enabled_alarm_kinds_defaults_to_all():
    assert set(parse_enabled_alarm_kinds(None)) == {
        "tunnel_down",
        "circuit_interruption",
        "sla_loss",
        "sla_latency",
        "utilization",
        "health",
        "circuit_flap",
    }
