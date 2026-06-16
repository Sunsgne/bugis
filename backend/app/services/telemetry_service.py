"""Telemetry & SLA computation.

Provides health scoring over collected samples and a simulator that generates
realistic samples so the operations dashboards have data without a live
SNMP/gNMI collector wired up.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit
from app.models.enums import CircuitStatus
from app.models.telemetry import TelemetrySample
from app.schemas.telemetry import CircuitHealth
from app.services import availability_service, snmp_telemetry
from app.services.telemetry_buckets import (
    BUCKET_MINUTES,
    aggregate_5min_buckets,
    p95_from_buckets,
    percentile,
)

# Raw telemetry samples are retained indefinitely (no TTL purge).


def record_sample(db: Session, **kwargs) -> TelemetrySample:
    sample = TelemetrySample(**kwargs)
    db.add(sample)
    db.flush()
    return sample


def collect_circuit_sample(
    db: Session,
    circuit: Circuit,
    *,
    interval_sec: float = 30.0,
) -> TelemetrySample:
    """Collect one sample via SNMP (or simulation) including traffic and latency."""
    traffic = snmp_telemetry.poll_circuit_traffic(
        db, circuit, interval_sec=interval_sec
    )
    loss = round(random.uniform(0, 0.4), 3) if traffic.tunnel_up else round(
        random.uniform(50, 100), 3
    )
    latency = round(random.uniform(1.5, 18.0), 2) if traffic.tunnel_up else 0.0
    jitter = round(random.uniform(0.1, 2.5), 2) if traffic.tunnel_up else 0.0
    state = "up" if traffic.tunnel_up else "down"

    sample = record_sample(
        db,
        circuit_id=circuit.id,
        rx_mbps=traffic.rx_mbps,
        tx_mbps=traffic.tx_mbps,
        utilization_pct=traffic.utilization_pct,
        latency_ms=latency,
        jitter_ms=jitter,
        packet_loss_pct=loss,
        errors=traffic.errors,
        tunnel_state=state,
    )
    availability_service.process_tunnel_state(
        db,
        circuit,
        tunnel_up=traffic.tunnel_up,
        source=traffic.source,
        at=sample.created_at,
    )
    return sample


def _parse_range(
    *,
    hours: int | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    if start_at and end_at:
        start = start_at.astimezone(timezone.utc) if start_at.tzinfo else start_at.replace(tzinfo=timezone.utc)
        end = end_at.astimezone(timezone.utc) if end_at.tzinfo else end_at.replace(tzinfo=timezone.utc)
        if end < start:
            start, end = end, start
        return start, end
    if hours is not None:
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=max(1, min(hours, 24 * 366)))
        return start, end
    return None, None


def query_circuit_samples(
    db: Session,
    circuit_id: int,
    *,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    hours: int | None = None,
    limit: int | None = None,
) -> list[TelemetrySample]:
    """Load raw samples oldest-first. No automatic deletion — full history kept."""
    range_start, range_end = _parse_range(
        hours=hours, start_at=start_at, end_at=end_at
    )
    stmt = select(TelemetrySample).where(TelemetrySample.circuit_id == circuit_id)
    if range_start is not None:
        stmt = stmt.where(TelemetrySample.created_at >= range_start)
    if range_end is not None:
        stmt = stmt.where(TelemetrySample.created_at <= range_end)
    stmt = stmt.order_by(TelemetrySample.created_at.asc(), TelemetrySample.id.asc())
    if limit is not None:
        limit = max(1, min(limit, 500_000))
        stmt = stmt.limit(limit)
    return list(db.execute(stmt).scalars().all())


def list_circuit_samples(
    db: Session,
    circuit_id: int,
    *,
    limit: int = 120,
    hours: int | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> list[TelemetrySample]:
    """Return samples oldest-first for charting (raw poll points)."""
    return query_circuit_samples(
        db,
        circuit_id,
        hours=hours,
        start_at=start_at,
        end_at=end_at,
        limit=max(1, min(limit, 2000)),
    )


def chart_p95(samples: list[TelemetrySample]) -> dict:
    buckets = aggregate_5min_buckets(samples)
    if buckets:
        return p95_from_buckets(buckets)
    rx = [s.rx_mbps for s in samples]
    tx = [s.tx_mbps for s in samples]
    rx95 = percentile(rx, 95)
    tx95 = percentile(tx, 95)
    return {
        "in_95_mbps": rx95,
        "out_95_mbps": tx95,
        "billable_95_mbps": max(rx95, tx95),
        "bucket_count": 0,
        "granularity_minutes": BUCKET_MINUTES,
    }


def traffic_summary(
    db: Session,
    circuit: Circuit,
    *,
    hours: int | None = 24,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: int | None = None,
) -> dict:
    """5-minute bucketed traffic series + 95th-percentile for the selected window."""
    samples = query_circuit_samples(
        db,
        circuit.id,
        hours=hours,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
    )
    buckets = aggregate_5min_buckets(samples)
    p95 = p95_from_buckets(buckets) if buckets else {
        "in_95_mbps": 0.0,
        "out_95_mbps": 0.0,
        "billable_95_mbps": 0.0,
        "bucket_count": 0,
        "granularity_minutes": BUCKET_MINUTES,
    }
    range_start, range_end = _parse_range(
        hours=hours, start_at=start_at, end_at=end_at
    )
    return {
        "circuit_id": circuit.id,
        "samples": samples,
        "buckets": [b.to_dict() for b in buckets],
        "p95": p95,
        "bandwidth_mbps": circuit.bandwidth_mbps,
        "granularity_minutes": BUCKET_MINUTES,
        "raw_sample_count": len(samples),
        "range_start": range_start.isoformat() if range_start else None,
        "range_end": range_end.isoformat() if range_end else None,
        "retention": "permanent",
    }


def simulate_circuit_sample(db: Session, circuit: Circuit) -> TelemetrySample:
    """Generate one plausible telemetry sample for an active circuit."""
    bw = max(circuit.bandwidth_mbps, 1)
    util = random.uniform(5, 85)
    tx = bw * util / 100.0
    rx = tx * random.uniform(0.6, 1.1)
    loss = round(random.uniform(0, 0.4), 3)
    latency = round(random.uniform(1.5, 18.0), 2)
    jitter = round(random.uniform(0.1, 2.5), 2)
    state = "up" if circuit.status == CircuitStatus.ACTIVE else "down"
    return record_sample(
        db,
        circuit_id=circuit.id,
        rx_mbps=round(rx, 2),
        tx_mbps=round(tx, 2),
        utilization_pct=round(util, 2),
        latency_ms=latency,
        jitter_ms=jitter,
        packet_loss_pct=loss,
        errors=random.randint(0, 3),
        tunnel_state=state,
    )


def _aggregate_overview_traffic(rows: list[TelemetrySample]) -> list[dict]:
    """Bucket samples by minute and circuit, then sum per-circuit averages."""
    per_circuit: dict[tuple[str, int], dict] = {}
    for s in rows:
        if not s.created_at or s.circuit_id is None:
            continue
        minute = s.created_at.strftime("%Y-%m-%d %H:%M")
        key = (minute, s.circuit_id)
        b = per_circuit.setdefault(
            key, {"rx": 0.0, "tx": 0.0, "lat": 0.0, "loss": 0.0, "n": 0}
        )
        b["rx"] += s.rx_mbps
        b["tx"] += s.tx_mbps
        b["lat"] += s.latency_ms
        b["loss"] += s.packet_loss_pct
        b["n"] += 1

    buckets: dict[str, dict] = {}
    for (minute, _), vals in per_circuit.items():
        n = max(vals["n"], 1)
        b = buckets.setdefault(
            minute,
            {"rx": 0.0, "tx": 0.0, "lat": 0.0, "loss": 0.0, "n": 0},
        )
        b["rx"] += vals["rx"] / n
        b["tx"] += vals["tx"] / n
        b["lat"] += vals["lat"]
        b["loss"] += vals["loss"]
        b["n"] += vals["n"]

    out = []
    for minute in sorted(buckets):
        b = buckets[minute]
        n = max(b["n"], 1)
        out.append({
            "t": minute[11:],
            "rx": round(b["rx"], 1),
            "tx": round(b["tx"], 1),
            "latency": round(b["lat"] / n, 2),
            "loss": round(b["loss"] / n, 3),
        })
    return out


def overview_traffic(
    db: Session,
    *,
    sample_limit: int = 2000,
    hours: int = 24,
) -> list[dict]:
    """Aggregate recent telemetry into a per-minute network-wide traffic trend.

    Each circuit contributes its per-minute average; minutes are keyed by full
    timestamp so samples from different days are never merged.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=max(1, min(hours, 24 * 7)))
    rows = db.execute(
        select(TelemetrySample)
        .where(TelemetrySample.created_at >= since)
        .order_by(TelemetrySample.id.desc())
        .limit(sample_limit)
    ).scalars().all()
    return _aggregate_overview_traffic(rows)[-40:]


def _percentile(values: list[float], pct: float) -> float:
    return percentile(values, pct)


def billing_95th(
    db: Session,
    circuit: Circuit,
    period: str | None = None,
    *,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> dict:
    """95th-percentile billing on 5-minute buckets (ISP 月95 / custom window)."""
    if start_at and end_at:
        samples = query_circuit_samples(
            db, circuit.id, start_at=start_at, end_at=end_at
        )
        sel_label = (
            f"{start_at.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M')} ~ "
            f"{end_at.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
        )
        available_months: list[str] = []
    else:
        samples = query_circuit_samples(db, circuit.id)
        by_month: dict[str, list[TelemetrySample]] = {}
        for s in samples:
            if not s.created_at:
                continue
            by_month.setdefault(s.created_at.strftime("%Y-%m"), []).append(s)
        available_months = sorted(by_month.keys(), reverse=True)
        sel = period if period in by_month else (available_months[0] if available_months else None)
        sel_label = sel
        samples = by_month.get(sel, [])

    buckets = aggregate_5min_buckets(samples)
    p95 = p95_from_buckets(buckets)
    rx = [b.rx_mbps for b in buckets]
    tx = [b.tx_mbps for b in buckets]
    billable = [b.billable_mbps for b in buckets]
    return {
        "circuit_id": circuit.id,
        "circuit_code": circuit.code,
        "period": sel_label,
        "available_months": available_months,
        "range_start": start_at.isoformat() if start_at else None,
        "range_end": end_at.isoformat() if end_at else None,
        "raw_samples": len(samples),
        "samples": len(buckets),
        "granularity_minutes": BUCKET_MINUTES,
        "bandwidth_mbps": circuit.bandwidth_mbps,
        "in_95_mbps": p95["in_95_mbps"],
        "out_95_mbps": p95["out_95_mbps"],
        "billable_95_mbps": p95["billable_95_mbps"],
        "peak_mbps": round(max(billable, default=0.0), 2),
        "avg_mbps": round(sum(billable) / len(billable), 2) if billable else 0.0,
        "utilization_pct": round(p95["billable_95_mbps"] / circuit.bandwidth_mbps * 100, 1)
        if circuit.bandwidth_mbps
        else 0.0,
        "retention": "permanent",
    }


def compute_health(db: Session, circuit: Circuit, limit: int = 100) -> CircuitHealth:
    samples = db.execute(
        select(TelemetrySample)
        .where(TelemetrySample.circuit_id == circuit.id)
        .order_by(TelemetrySample.id.desc())
        .limit(limit)
    ).scalars().all()

    n = len(samples)
    if n == 0:
        return CircuitHealth(
            circuit_id=circuit.id,
            circuit_code=circuit.code,
            status=circuit.status.value,
            sla_target=circuit.sla_target,
            bandwidth_mbps=circuit.bandwidth_mbps,
            samples=0,
            health_score=100.0 if circuit.status == CircuitStatus.ACTIVE else 0.0,
        )

    avg_lat = sum(s.latency_ms for s in samples) / n
    avg_jit = sum(s.jitter_ms for s in samples) / n
    avg_loss = sum(s.packet_loss_pct for s in samples) / n
    avg_util = sum(s.utilization_pct for s in samples) / n
    peak_util = max(s.utilization_pct for s in samples)
    latest = samples[0]
    tunnel_down = latest.tunnel_state == "down"

    # Simple weighted health score (0-100).
    score = 100.0
    score -= min(avg_loss * 40, 40)          # loss dominates
    score -= min(max(avg_lat - 10, 0) * 1.5, 20)
    score -= min(avg_jit * 3, 15)
    score -= min(max(peak_util - 90, 0) * 1.0, 15)
    if circuit.status != CircuitStatus.ACTIVE:
        score = min(score, 50)
    if tunnel_down:
        score = min(score, 30)
    score = max(0.0, round(score, 1))

    return CircuitHealth(
        circuit_id=circuit.id,
        circuit_code=circuit.code,
        status=circuit.status.value,
        sla_target=circuit.sla_target,
        avg_latency_ms=round(avg_lat, 2),
        avg_jitter_ms=round(avg_jit, 2),
        avg_packet_loss_pct=round(avg_loss, 3),
        avg_utilization_pct=round(avg_util, 2),
        peak_utilization_pct=round(peak_util, 2),
        bandwidth_mbps=circuit.bandwidth_mbps,
        samples=n,
        health_score=score,
        tunnel_down=tunnel_down,
    )
