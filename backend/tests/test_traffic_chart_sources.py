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


def test_traffic_summary_falls_back_to_raw_when_aggregate_empty(db_session, monkeypatch):
    circuit = _make_circuit(db_session)
    base = datetime.now(timezone.utc) - timedelta(minutes=5)
    db_session.add(
        TelemetrySample(
            circuit_id=circuit.id,
            rx_mbps=12.0,
            tx_mbps=8.0,
            latency_ms=0.0,
            utilization_pct=12.0,
            tunnel_state="up",
            source="snmp",
            created_at=base,
        )
    )
    db_session.add(
        TelemetrySample(
            circuit_id=circuit.id,
            rx_mbps=0.0,
            tx_mbps=0.0,
            latency_ms=21.0,
            jitter_ms=0.3,
            packet_loss_pct=0.0,
            utilization_pct=0.0,
            tunnel_state="up",
            source="probe",
            created_at=base + timedelta(seconds=10),
        )
    )
    db_session.commit()

    monkeypatch.setattr(
        telemetry_service.telemetry_timescale,
        "continuous_aggregate_available",
        lambda _db: True,
    )
    monkeypatch.setattr(
        telemetry_service.telemetry_timescale,
        "should_use_continuous_aggregate",
        lambda _hours: True,
    )
    monkeypatch.setattr(
        telemetry_service.telemetry_timescale,
        "fetch_traffic_buckets",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        telemetry_service.telemetry_timescale,
        "fetch_latency_buckets",
        lambda *_args, **_kwargs: [],
    )

    payload = telemetry_service.traffic_summary_payload(
        db_session, circuit, hours=24, limit=20
    )
    assert payload["resolution"] == "raw"
    assert len(payload["samples"]) == 1
    assert payload["samples"][0].rx_mbps == 12.0
    assert len(payload["qos_samples"]) == 1
    assert payload["qos_samples"][0].latency_ms == 21.0


def test_traffic_summary_falls_back_when_aggregate_zeros(db_session, monkeypatch):
    circuit = _make_circuit(db_session)
    base = datetime.now(timezone.utc) - timedelta(minutes=5)
    db_session.add(
        TelemetrySample(
            circuit_id=circuit.id,
            rx_mbps=45.0,
            tx_mbps=30.0,
            latency_ms=0.0,
            utilization_pct=45.0,
            tunnel_state="up",
            source="snmp",
            created_at=base,
        )
    )
    db_session.add(
        TelemetrySample(
            circuit_id=circuit.id,
            rx_mbps=0.0,
            tx_mbps=0.0,
            latency_ms=18.0,
            jitter_ms=0.2,
            packet_loss_pct=0.0,
            utilization_pct=0.0,
            tunnel_state="up",
            source="probe",
            created_at=base + timedelta(seconds=10),
        )
    )
    db_session.commit()

    zero_bucket = {
        "bucket": base.replace(second=0, microsecond=0),
        "rx_mbps": 0.0,
        "tx_mbps": 0.0,
        "sample_count": 1,
    }
    latency_bucket = {
        "bucket": base.replace(second=0, microsecond=0),
        "latency_ms": 18.0,
        "avg_latency_ms": 18.0,
        "sample_count": 1,
    }

    monkeypatch.setattr(
        telemetry_service.telemetry_timescale,
        "continuous_aggregate_available",
        lambda _db: True,
    )
    monkeypatch.setattr(
        telemetry_service.telemetry_timescale,
        "should_use_continuous_aggregate",
        lambda _hours: True,
    )
    monkeypatch.setattr(
        telemetry_service.telemetry_timescale,
        "fetch_traffic_buckets",
        lambda *_args, **_kwargs: [zero_bucket],
    )
    monkeypatch.setattr(
        telemetry_service.telemetry_timescale,
        "fetch_latency_buckets",
        lambda *_args, **_kwargs: [latency_bucket],
    )

    payload = telemetry_service.traffic_summary_payload(
        db_session, circuit, hours=24, limit=20
    )
    assert payload["resolution"] == "raw"
    assert len(payload["samples"]) == 1
    assert payload["samples"][0].rx_mbps == 45.0
    assert len(payload["qos_samples"]) == 1
    assert payload["qos_samples"][0]["latency_ms"] == 18.0


def test_billing_95th_scopes_to_selected_month(db_session):
    circuit = _make_circuit(db_session)
    old = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
    new = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    db_session.add(
        TelemetrySample(
            circuit_id=circuit.id,
            rx_mbps=900.0,
            tx_mbps=900.0,
            utilization_pct=90.0,
            tunnel_state="up",
            source="snmp",
            created_at=old,
        )
    )
    db_session.add(
        TelemetrySample(
            circuit_id=circuit.id,
            rx_mbps=50.0,
            tx_mbps=50.0,
            utilization_pct=5.0,
            tunnel_state="up",
            source="snmp",
            created_at=new,
        )
    )
    db_session.commit()

    june = telemetry_service.billing_95th(db_session, circuit, period="2026-06")
    assert june["period"] == "2026-06"
    assert june["samples"] == 1
    assert june["billable_95_mbps"] == 50.0
    assert "2026-05" in june["available_months"]
    assert "2026-06" in june["available_months"]


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
