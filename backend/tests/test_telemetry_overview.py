"""Tests for dashboard traffic aggregation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.models.telemetry import TelemetrySample
from app.services import telemetry_service
from app.services.telemetry_service import _aggregate_overview_traffic


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _sample(
    circuit_id: int,
    *,
    rx: float,
    tx: float,
    at: datetime,
    source: str = "snmp",
) -> TelemetrySample:
    return TelemetrySample(
        circuit_id=circuit_id,
        rx_mbps=rx,
        tx_mbps=tx,
        utilization_pct=50.0,
        latency_ms=5.0,
        jitter_ms=0.5,
        packet_loss_pct=0.01,
        errors=0,
        tunnel_state="up",
        source=source,
        created_at=at,
    )


def test_overview_traffic_does_not_sum_across_days():
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    yesterday = now - timedelta(days=1)
    minute_key = now.strftime("%H:%M")

    rows = [
        _sample(1, rx=100, tx=100, at=yesterday),
        _sample(2, rx=100, tx=100, at=now),
    ]
    by_time = {r["t"]: r for r in _aggregate_overview_traffic(rows)}
    assert minute_key in by_time
    assert by_time[minute_key]["rx"] == 100.0
    assert by_time[minute_key]["tx"] == 100.0


def test_overview_traffic_averages_per_circuit_then_sums():
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    rows = [
        _sample(1, rx=100, tx=80, at=now),
        _sample(1, rx=200, tx=120, at=now + timedelta(seconds=10)),
        _sample(2, rx=50, tx=50, at=now),
    ]
    latest = _aggregate_overview_traffic(rows)[-1]
    assert latest["rx"] == 200.0
    assert latest["tx"] == 150.0


def test_overview_traffic_minute_path_sums_all_circuits(db_session):
    """Regression: LIMIT+DESC sampling could drop circuits and dip the chart to ~0."""
    import uuid

    from app.models.circuit import Circuit
    from app.models.enums import CircuitStatus, ServiceType
    from app.models.tenant import Tenant

    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(name=f"T {suffix}", code=f"T{suffix}")
    db_session.add(tenant)
    db_session.flush()

    circuits = []
    for idx in range(3):
        circuit = Circuit(
            code=f"CIR-OVR-{suffix}-{idx}",
            name=f"Overview {idx}",
            tenant_id=tenant.id,
            service_type=ServiceType.L2VPN_EVPN,
            status=CircuitStatus.ACTIVE,
            bandwidth_mbps=1000,
        )
        db_session.add(circuit)
        circuits.append(circuit)
    db_session.flush()

    for circuit in circuits:
        db_session.add(
            _sample(circuit.id, rx=100.0, tx=50.0, at=now + timedelta(seconds=5))
        )
    db_session.commit()

    with patch.object(
        telemetry_service.telemetry_timescale,
        "continuous_aggregate_available",
        return_value=False,
    ):
        buckets = telemetry_service.overview_traffic(db_session, hours=1)

    assert buckets
    latest = buckets[-1]
    assert latest["rx"] == 300.0
    assert latest["tx"] == 150.0
