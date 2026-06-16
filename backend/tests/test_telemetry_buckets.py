"""Tests for 5-minute telemetry buckets and 95 billing."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.telemetry import TelemetrySample
from app.services.telemetry_buckets import aggregate_5min_buckets, p95_from_buckets


def _sample(at: datetime, rx: float, tx: float) -> TelemetrySample:
    return TelemetrySample(
        circuit_id=1,
        rx_mbps=rx,
        tx_mbps=tx,
        utilization_pct=0,
        latency_ms=1,
        jitter_ms=0.1,
        packet_loss_pct=0,
        created_at=at,
    )


def test_aggregate_5min_buckets_averages_raw_polls():
    base = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
    samples = [
        _sample(base + timedelta(seconds=0), 100, 200),
        _sample(base + timedelta(seconds=30), 300, 400),
        _sample(base + timedelta(minutes=6), 500, 600),
    ]
    buckets = aggregate_5min_buckets(samples)
    assert len(buckets) == 2
    assert buckets[0].rx_mbps == 200
    assert buckets[0].tx_mbps == 300
    assert buckets[1].rx_mbps == 500


def test_p95_from_5min_buckets():
    base = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    samples = []
    for i in range(100):
        samples.append(
            _sample(
                base + timedelta(minutes=i * 5),
                float(100 + i),
                float(50 + i),
            )
        )
    buckets = aggregate_5min_buckets(samples)
    p95 = p95_from_buckets(buckets)
    assert p95["bucket_count"] == 100
    assert p95["granularity_minutes"] == 5
    assert p95["billable_95_mbps"] >= 150
