"""Tests for per-circuit SLA alarm threshold overrides."""
from __future__ import annotations

import uuid

import pytest

from app.models.circuit import Circuit
from app.models.enums import CircuitStatus, ServiceType
from app.models.platform_settings import PlatformSettings
from app.models.tenant import Tenant
from app.schemas.telemetry import CircuitHealth
from app.services import alarm_service
from app.services.circuit_alarm_settings import effective_thresholds


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


@pytest.fixture
def sample_circuit(db_session):
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(name=f"Alarm Tenant {suffix}", code=f"ALM{suffix}")
    db_session.add(tenant)
    db_session.flush()
    circuit = Circuit(
        name="Alarm Circuit",
        code=f"ALM-{suffix}",
        tenant_id=tenant.id,
        service_type=ServiceType.L2VPN_EVPN,
        status=CircuitStatus.ACTIVE,
        bandwidth_mbps=100,
        alarm_latency_ms=250.0,
        alarm_packet_loss_pct=2.0,
    )
    db_session.add(circuit)
    db_session.commit()
    db_session.refresh(circuit)
    return circuit


def test_effective_thresholds_use_circuit_overrides(sample_circuit, platform_row):
    th = effective_thresholds(sample_circuit, platform_row)
    assert th.latency_ms == 250.0
    assert th.packet_loss_pct == 2.0
    assert th.utilization_pct == platform_row.threshold_utilization_pct
    assert th.health_score_min == platform_row.threshold_health_score


def test_effective_thresholds_fallback_to_platform(sample_circuit, platform_row):
    sample_circuit.alarm_latency_ms = None
    sample_circuit.alarm_packet_loss_pct = None
    th = effective_thresholds(sample_circuit, platform_row)
    assert th.latency_ms == platform_row.threshold_latency_ms
    assert th.packet_loss_pct == platform_row.threshold_packet_loss_pct


def test_evaluate_circuit_health_respects_circuit_latency_threshold(
    db_session, sample_circuit, platform_row
):
    health = CircuitHealth(
        circuit_id=sample_circuit.id,
        circuit_code=sample_circuit.code,
        status="active",
        avg_latency_ms=120.0,
        avg_jitter_ms=0.0,
        avg_packet_loss_pct=0.0,
        avg_utilization_pct=1.0,
        peak_utilization_pct=1.0,
        bandwidth_mbps=100,
        samples=5,
        qos_samples=1,
        health_score=90.0,
        tunnel_down=False,
    )
    alarm_service.evaluate_circuit_health(db_session, sample_circuit, health)
    db_session.flush()
    assert alarm_service._active_by_key(db_session, f"circuit:{sample_circuit.id}:latency") is None

    health_high = health.model_copy(update={"avg_latency_ms": 280.0, "health_score": 40.0})
    alarm_service.evaluate_circuit_health(db_session, sample_circuit, health_high)
    db_session.flush()
    lat_alarm = alarm_service._active_by_key(
        db_session, f"circuit:{sample_circuit.id}:latency"
    )
    assert lat_alarm is not None
    assert "280" in lat_alarm.title
