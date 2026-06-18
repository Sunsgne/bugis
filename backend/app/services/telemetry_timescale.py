"""TimescaleDB helpers for telemetry_samples continuous aggregates."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings

_TS_CACHE: bool | None = None
_TRAFFIC_SOURCES = ("snmp", "traffic_only", "simulated", "manual", "snmp-link")


def timescale_enabled(db: Session) -> bool:
    global _TS_CACHE
    if _TS_CACHE is not None:
        return _TS_CACHE
    try:
        row = db.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb' LIMIT 1")
        ).fetchone()
        _TS_CACHE = row is not None
    except Exception:
        _TS_CACHE = False
    return _TS_CACHE


def continuous_aggregate_available(db: Session) -> bool:
    if not timescale_enabled(db):
        return False
    try:
        row = db.execute(
            text(
                """
                SELECT 1 FROM timescaledb_information.continuous_aggregates
                WHERE view_name = 'telemetry_samples_5m'
                LIMIT 1
                """
            )
        ).fetchone()
        return row is not None
    except Exception:
        return False


def should_use_continuous_aggregate(hours: int) -> bool:
    settings = get_settings()
    return hours > settings.telemetry_aggregate_after_hours


def fetch_traffic_buckets(
    db: Session,
    *,
    circuit_id: int,
    hours: int,
) -> list[dict[str, Any]]:
    """Return chart points from 5m continuous aggregate (max rx/tx per bucket)."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = db.execute(
        text(
            """
            SELECT
              bucket,
              MAX(max_rx_mbps) AS max_rx_mbps,
              MAX(max_tx_mbps) AS max_tx_mbps,
              SUM(sample_count) AS sample_count
            FROM telemetry_samples_5m
            WHERE circuit_id = :cid
              AND bucket >= :since
              AND source = ANY(:sources)
            GROUP BY bucket
            ORDER BY bucket ASC
            """
        ),
        {"cid": circuit_id, "since": since, "sources": list(_TRAFFIC_SOURCES)},
    ).mappings().all()

    return [
        {
            "bucket": row["bucket"],
            "rx_mbps": float(row["max_rx_mbps"] or 0),
            "tx_mbps": float(row["max_tx_mbps"] or 0),
            "sample_count": int(row["sample_count"] or 0),
        }
        for row in rows
    ]


def fetch_latency_buckets(
    db: Session,
    *,
    circuit_id: int,
    hours: int,
) -> list[dict[str, Any]]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = db.execute(
        text(
            """
            SELECT bucket, max_latency_ms, avg_latency_ms, sample_count
            FROM telemetry_samples_5m
            WHERE circuit_id = :cid
              AND source = 'probe'
              AND bucket >= :since
              AND max_latency_ms > 0
            ORDER BY bucket ASC
            """
        ),
        {"cid": circuit_id, "since": since},
    ).mappings().all()

    return [
        {
            "bucket": row["bucket"],
            "latency_ms": float(row["max_latency_ms"] or 0),
            "avg_latency_ms": float(row["avg_latency_ms"] or 0),
            "sample_count": int(row["sample_count"] or 0),
        }
        for row in rows
    ]


def fetch_billing_months(db: Session, *, circuit_id: int) -> list[str]:
    rows = db.execute(
        text(
            """
            SELECT DISTINCT to_char(bucket, 'YYYY-MM') AS month
            FROM telemetry_samples_5m
            WHERE circuit_id = :cid
              AND source = ANY(:sources)
            ORDER BY month DESC
            """
        ),
        {"cid": circuit_id, "sources": list(_TRAFFIC_SOURCES)},
    ).scalars().all()
    return list(rows)


def fetch_billing_95th_from_aggregate(
    db: Session,
    *,
    circuit_id: int,
    month_start: datetime,
    month_end: datetime,
) -> dict[str, Any]:
    """Monthly 95th percentile from 5m max(rx/tx) buckets."""
    rows = db.execute(
        text(
            """
            SELECT
              bucket,
              MAX(max_rx_mbps) AS max_rx_mbps,
              MAX(max_tx_mbps) AS max_tx_mbps
            FROM telemetry_samples_5m
            WHERE circuit_id = :cid
              AND bucket >= :start
              AND bucket < :end
              AND source = ANY(:sources)
            GROUP BY bucket
            ORDER BY bucket ASC
            """
        ),
        {
            "cid": circuit_id,
            "start": month_start,
            "end": month_end,
            "sources": list(_TRAFFIC_SOURCES),
        },
    ).mappings().all()

    rx_vals = sorted(float(r["max_rx_mbps"] or 0) for r in rows)
    tx_vals = sorted(float(r["max_tx_mbps"] or 0) for r in rows)

    def p95(vals: list[float]) -> float:
        if not vals:
            return 0.0
        idx = max(0, int(len(vals) * 0.95) - 1)
        return round(vals[idx], 2)

    rx95 = p95(rx_vals)
    tx95 = p95(tx_vals)
    peak = round(max([*rx_vals, *tx_vals], default=0.0), 2)
    avg = round((sum(rx_vals) + sum(tx_vals)) / (2 * len(rows)), 2) if rows else 0.0
    return {
        "samples": len(rows),
        "in_95_mbps": rx95,
        "out_95_mbps": tx95,
        "billable_95_mbps": max(rx95, tx95),
        "peak_mbps": peak,
        "avg_mbps": avg,
        "source": "continuous_aggregate_5m",
    }
