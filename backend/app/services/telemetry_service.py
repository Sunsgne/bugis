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


def list_circuit_samples(
    db: Session,
    circuit_id: int,
    *,
    limit: int = 120,
    hours: int | None = None,
) -> list[TelemetrySample]:
    """Return samples oldest-first for charting."""
    limit = max(1, min(limit, 2000))
    stmt = (
        select(TelemetrySample)
        .where(TelemetrySample.circuit_id == circuit_id)
        .order_by(TelemetrySample.id.desc())
        .limit(limit)
    )
    if hours is not None:
        since = datetime.now(timezone.utc) - timedelta(hours=max(1, min(hours, 24 * 30)))
        stmt = (
            select(TelemetrySample)
            .where(
                TelemetrySample.circuit_id == circuit_id,
                TelemetrySample.created_at >= since,
            )
            .order_by(TelemetrySample.id.desc())
            .limit(limit)
        )
    rows = list(db.execute(stmt).scalars().all())
    rows.reverse()
    return rows


def chart_p95(samples: list[TelemetrySample]) -> dict:
    rx = [s.rx_mbps for s in samples]
    tx = [s.tx_mbps for s in samples]
    rx95 = _percentile(rx, 95)
    tx95 = _percentile(tx, 95)
    return {
        "in_95_mbps": rx95,
        "out_95_mbps": tx95,
        "billable_95_mbps": max(rx95, tx95),
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
    if not values:
        return 0.0
    s = sorted(values)
    import math
    idx = max(0, math.ceil(pct / 100 * len(s)) - 1)
    return round(s[idx], 2)


def billing_95th(db: Session, circuit: Circuit, period: str | None = None) -> dict:
    """95th-percentile (月95) bandwidth billing for a circuit.

    Buckets samples by month; for the selected month computes the 95th
    percentile of inbound and outbound, billing the higher (ISP convention).
    """
    samples = db.execute(
        select(TelemetrySample).where(TelemetrySample.circuit_id == circuit.id)
    ).scalars().all()

    by_month: dict[str, list[TelemetrySample]] = {}
    for s in samples:
        if not s.created_at:
            continue
        by_month.setdefault(s.created_at.strftime("%Y-%m"), []).append(s)

    months = sorted(by_month.keys(), reverse=True)
    sel = period if period in by_month else (months[0] if months else None)
    rows = by_month.get(sel, [])

    rx = [s.rx_mbps for s in rows]
    tx = [s.tx_mbps for s in rows]
    rx95 = _percentile(rx, 95)
    tx95 = _percentile(tx, 95)
    return {
        "circuit_id": circuit.id,
        "circuit_code": circuit.code,
        "period": sel,
        "available_months": months,
        "samples": len(rows),
        "bandwidth_mbps": circuit.bandwidth_mbps,
        "in_95_mbps": rx95,
        "out_95_mbps": tx95,
        "billable_95_mbps": max(rx95, tx95),
        "peak_mbps": round(max([*rx, *tx], default=0.0), 2),
        "avg_mbps": round((sum(rx) + sum(tx)) / (2 * len(rows)), 2) if rows else 0.0,
        "utilization_pct": round(max(rx95, tx95) / circuit.bandwidth_mbps * 100, 1)
        if circuit.bandwidth_mbps else 0.0,
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
