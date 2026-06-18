"""Traffic charts must exclude QoS-only probe samples (rx/tx always zero)."""
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


def _make_circuit(db_session) -> Circuit:
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(name=f"T {suffix}", code=f"T{suffix}")
    db_session.add(tenant)
    db_session.flush()
    circuit = Circuit(
        name="Traffic Chart Circuit",
        code=f"TRF-{suffix}",
        tenant_id=tenant.id,
        service_type=ServiceType.L2VPN_EVPN,
        status=CircuitStatus.ACTIVE,
        bandwidth_mbps=1000,
    )
    db_session.add(circuit)
    db_session.flush()
    return circuit


def test_traffic_summary_excludes_probe_zeros(db_session):
    circuit = _make_circuit(db_session)
    base = datetime.now(timezone.utc) - timedelta(minutes=10)

    for i in range(6):
        ts = base + timedelta(seconds=30 * i)
        db_session.add(
            TelemetrySample(
                circuit_id=circuit.id,
                rx_mbps=80.0,
                tx_mbps=60.0,
                latency_ms=2.0,
                jitter_ms=0.2,
                packet_loss_pct=0.0,
                utilization_pct=8.0,
                tunnel_state="up",
                source="snmp",
                created_at=ts,
            )
        )
        db_session.add(
            TelemetrySample(
                circuit_id=circuit.id,
                rx_mbps=0.0,
                tx_mbps=0.0,
                latency_ms=5.0,
                jitter_ms=0.5,
                packet_loss_pct=0.1,
                utilization_pct=0.0,
                tunnel_state="up",
                source="probe",
                created_at=ts + timedelta(seconds=5),
            )
        )
    db_session.commit()

    all_rows = telemetry_service.list_circuit_samples(
        db_session, circuit.id, hours=24, limit=20
    )
    traffic_rows = telemetry_service.list_circuit_samples(
        db_session, circuit.id, hours=24, limit=20, traffic_only=True
    )

    assert len(all_rows) == 12
    assert len(traffic_rows) == 6
    assert all(s.source == "snmp" for s in traffic_rows)
    assert all(s.rx_mbps == 80.0 for s in traffic_rows)

    p95_all = telemetry_service.chart_p95(all_rows)
    p95_traffic = telemetry_service.chart_p95(traffic_rows)
    assert p95_all["billable_95_mbps"] == 80.0
    assert p95_traffic["billable_95_mbps"] == 80.0

    health = telemetry_service.compute_health(
        db_session, circuit, limit=20, hours=24
    )
    assert health.avg_utilization_pct == 8.0
    assert health.peak_utilization_pct == 8.0
    assert health.qos_samples == 6


def test_traffic_summary_includes_qos_samples(db_session):
    circuit = _make_circuit(db_session)
    base = datetime.now(timezone.utc) - timedelta(minutes=10)

    for i in range(3):
        ts = base + timedelta(seconds=30 * i)
        db_session.add(
            TelemetrySample(
                circuit_id=circuit.id,
                rx_mbps=80.0,
                tx_mbps=60.0,
                latency_ms=0.0,
                utilization_pct=8.0,
                tunnel_state="up",
                source="snmp",
                created_at=ts,
            )
        )
        db_session.add(
            TelemetrySample(
                circuit_id=circuit.id,
                rx_mbps=0.0,
                tx_mbps=0.0,
                latency_ms=12.0 + i,
                jitter_ms=0.5,
                packet_loss_pct=0.1,
                utilization_pct=0.0,
                tunnel_state="up",
                source="probe",
                created_at=ts + timedelta(seconds=5),
            )
        )
    db_session.commit()

    payload = telemetry_service.traffic_summary_payload(
        db_session, circuit, hours=24, limit=20
    )
    assert len(payload["samples"]) == 3
    assert all(s.source == "snmp" for s in payload["samples"])
    assert len(payload["qos_samples"]) == 3
    assert payload["qos_samples"][0].latency_ms == 12.0


def test_overview_aggregation_ignores_probe_traffic(db_session):
    circuit = _make_circuit(db_session)
    minute = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    snmp = TelemetrySample(
        circuit_id=circuit.id,
        rx_mbps=100.0,
        tx_mbps=50.0,
        latency_ms=1.0,
        jitter_ms=0.1,
        packet_loss_pct=0.0,
        utilization_pct=10.0,
        tunnel_state="up",
        source="snmp",
        created_at=minute,
    )
    probe = TelemetrySample(
        circuit_id=circuit.id,
        rx_mbps=0.0,
        tx_mbps=0.0,
        latency_ms=4.0,
        jitter_ms=0.4,
        packet_loss_pct=0.2,
        utilization_pct=0.0,
        tunnel_state="up",
        source="probe",
        created_at=minute + timedelta(seconds=15),
    )
    db_session.add(snmp)
    db_session.add(probe)
    db_session.commit()

    buckets = telemetry_service._aggregate_overview_traffic([snmp, probe])
    assert len(buckets) == 1
    assert buckets[0]["rx"] == 100.0
    assert buckets[0]["tx"] == 50.0
    assert buckets[0]["latency"] == 4.0
