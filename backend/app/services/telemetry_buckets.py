"""Telemetry bucket aggregation for 5-minute 95th-percentile billing."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.models.telemetry import TelemetrySample

BUCKET_MINUTES = 5


@dataclass
class TrafficBucket:
    bucket_at: datetime
    rx_mbps: float
    tx_mbps: float
    sample_count: int

    @property
    def billable_mbps(self) -> float:
        return max(self.rx_mbps, self.tx_mbps)

    def to_dict(self) -> dict:
        return {
            "bucket_at": self.bucket_at.isoformat(),
            "t": self.bucket_at.strftime("%m-%d %H:%M"),
            "rx_mbps": self.rx_mbps,
            "tx_mbps": self.tx_mbps,
            "billable_mbps": self.billable_mbps,
            "sample_count": self.sample_count,
        }


def floor_to_bucket(ts: datetime, minutes: int = BUCKET_MINUTES) -> datetime:
    ts = ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    minute = (ts.minute // minutes) * minutes
    return ts.replace(minute=minute, second=0, microsecond=0)


def aggregate_5min_buckets(samples: list[TelemetrySample]) -> list[TrafficBucket]:
    """Collapse raw poll samples into fixed 5-minute buckets (average per bucket)."""
    grouped: dict[datetime, dict] = {}
    for sample in samples:
        if not sample.created_at:
            continue
        key = floor_to_bucket(sample.created_at)
        bucket = grouped.setdefault(key, {"rx": 0.0, "tx": 0.0, "n": 0})
        bucket["rx"] += sample.rx_mbps
        bucket["tx"] += sample.tx_mbps
        bucket["n"] += 1

    buckets: list[TrafficBucket] = []
    for bucket_at in sorted(grouped):
        vals = grouped[bucket_at]
        n = max(vals["n"], 1)
        buckets.append(
            TrafficBucket(
                bucket_at=bucket_at,
                rx_mbps=round(vals["rx"] / n, 2),
                tx_mbps=round(vals["tx"] / n, 2),
                sample_count=vals["n"],
            )
        )
    return buckets


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    import math

    s = sorted(values)
    idx = max(0, math.ceil(pct / 100 * len(s)) - 1)
    return round(s[idx], 2)


def p95_from_buckets(buckets: list[TrafficBucket]) -> dict:
    rx = [b.rx_mbps for b in buckets]
    tx = [b.tx_mbps for b in buckets]
    rx95 = percentile(rx, 95)
    tx95 = percentile(tx, 95)
    return {
        "in_95_mbps": rx95,
        "out_95_mbps": tx95,
        "billable_95_mbps": max(rx95, tx95),
        "bucket_count": len(buckets),
        "granularity_minutes": BUCKET_MINUTES,
    }
