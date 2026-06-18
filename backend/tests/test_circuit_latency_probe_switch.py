"""Tests for per-circuit latency probe enable switch."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.models.circuit import Circuit
from app.models.enums import CircuitStatus, ServiceType
from app.models.platform_settings import PlatformSettings
from app.models.tenant import Tenant
from app.schemas.telemetry import CircuitHealth
from app.services import alarm_service, telemetry_service
from app.scheduler import _probe_one_circuit


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
def active_circuit(db_session):
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(name=f"Probe Switch Tenant {suffix}", code=f"PSW{suffix}")
    db_session.add(tenant)
    db_session.flush()
    circuit = Circuit(
        name="Probe Switch Circuit",
        code=f"PSW-{suffix}",
        tenant_id=tenant.id,
        service_type=ServiceType.L2VPN_EVPN,
        status=CircuitStatus.ACTIVE,
        bandwidth_mbps=100,
        latency_probe_enabled=False,
    )
    db_session.add(circuit)
    db_session.commit()
    db_session.refresh(circuit)
    return circuit


def test_scheduler_skips_disabled_circuit(db_session, active_circuit):
    from app.core.config import settings

    enabled = Circuit(
        name="Enabled",
        code=f"EN-{uuid.uuid4().hex[:6]}",
        tenant_id=active_circuit.tenant_id,
        service_type=ServiceType.L2VPN_EVPN,
        status=CircuitStatus.ACTIVE,
        bandwidth_mbps=100,
        latency_probe_enabled=True,
    )
    db_session.add(enabled)
    db_session.commit()

    with patch("app.services.circuit_probe.runner.probe_circuit") as mock_probe, patch.object(
        settings, "dry_run", False
    ):
        result = _probe_one_circuit(db_session, [active_circuit, enabled])
        assert result >= 1
        mock_probe.assert_called()
        assert mock_probe.call_args[0][1].id == enabled.id


def test_probe_api_rejects_disabled_circuit(client, auth_headers, active_circuit):
    resp = client.post(
        f"/api/v1/circuits/{active_circuit.id}/probe",
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "关闭" in resp.json()["detail"]


def test_collect_sample_ignores_probe_qos_when_disabled(db_session, active_circuit):
    from app.models.telemetry import TelemetrySample
    from datetime import datetime, timezone

    db_session.add(
        TelemetrySample(
            circuit_id=active_circuit.id,
            rx_mbps=0,
            tx_mbps=0,
            utilization_pct=0,
            latency_ms=88.0,
            jitter_ms=5.0,
            packet_loss_pct=1.5,
            source="probe",
            created_at=datetime.now(timezone.utc),
        )
    )
    db_session.flush()

    with patch("app.services.snmp_telemetry.poll_circuit_traffic") as mock_traffic:
        mock_traffic.return_value = type(
            "T",
            (),
            {
                "source": "snmp",
                "rx_mbps": 10.0,
                "tx_mbps": 8.0,
                "utilization_pct": 20.0,
                "errors": 0,
                "tunnel_up": True,
            },
        )()
        sample = telemetry_service.collect_circuit_sample(db_session, active_circuit)
        assert sample is not None
        assert sample.latency_ms == 0.0
        assert sample.jitter_ms == 0.0
        assert sample.packet_loss_pct == 0.0


def test_evaluate_health_clears_latency_alarms_when_disabled(
    db_session, active_circuit, platform_row
):
    health = CircuitHealth(
        circuit_id=active_circuit.id,
        circuit_code=active_circuit.code,
        status="active",
        bandwidth_mbps=100,
        samples=10,
        qos_samples=0,
        avg_latency_ms=999.0,
        avg_jitter_ms=0.0,
        avg_packet_loss_pct=99.0,
        avg_utilization_pct=10.0,
        peak_utilization_pct=20.0,
        health_score=50.0,
    )
    alarm_service.evaluate_circuit_health(db_session, active_circuit, health)
    db_session.flush()
    from app.models.alarm import Alarm
    from sqlalchemy import select

    rows = db_session.execute(
        select(Alarm).where(Alarm.circuit_id == active_circuit.id)
    ).scalars().all()
    kinds = {a.kind for a in rows if a.status != "cleared"}
    assert "sla_latency" not in kinds
    assert "sla_loss" not in kinds
