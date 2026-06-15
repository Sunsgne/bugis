"""Tests for dashboard traffic aggregation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.telemetry import TelemetrySample
from app.services.telemetry_service import _aggregate_overview_traffic


def _sample(
    circuit_id: int,
    *,
    rx: float,
    tx: float,
    at: datetime,
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
