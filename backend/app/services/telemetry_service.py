"""Telemetry & SLA computation.

Provides health scoring over collected samples and a simulator that generates
realistic samples so the operations dashboards have data without a live
SNMP/gNMI collector wired up.
"""
from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit
from app.models.enums import CircuitStatus
from app.models.telemetry import TelemetrySample
from app.schemas.telemetry import CircuitHealth


def record_sample(db: Session, **kwargs) -> TelemetrySample:
    sample = TelemetrySample(**kwargs)
    db.add(sample)
    db.flush()
    return sample


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


def overview_traffic(db: Session, sample_limit: int = 800) -> list[dict]:
    """Aggregate recent telemetry samples into a per-minute traffic trend.

    DB-agnostic: buckets the most recent samples by minute in Python.
    """
    rows = db.execute(
        select(TelemetrySample)
        .order_by(TelemetrySample.id.desc())
        .limit(sample_limit)
    ).scalars().all()
    buckets: dict[str, dict] = {}
    for s in rows:
        if not s.created_at:
            continue
        key = s.created_at.strftime("%H:%M")
        b = buckets.setdefault(
            key, {"t": key, "rx": 0.0, "tx": 0.0, "lat": 0.0, "loss": 0.0, "n": 0}
        )
        b["rx"] += s.rx_mbps
        b["tx"] += s.tx_mbps
        b["lat"] += s.latency_ms
        b["loss"] += s.packet_loss_pct
        b["n"] += 1
    out = []
    for b in buckets.values():
        n = max(b["n"], 1)
        out.append({
            "t": b["t"],
            "rx": round(b["rx"], 1),
            "tx": round(b["tx"], 1),
            "latency": round(b["lat"] / n, 2),
            "loss": round(b["loss"] / n, 3),
        })
    out.sort(key=lambda x: x["t"])
    return out[-40:]


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

    # Simple weighted health score (0-100).
    score = 100.0
    score -= min(avg_loss * 40, 40)          # loss dominates
    score -= min(max(avg_lat - 10, 0) * 1.5, 20)
    score -= min(avg_jit * 3, 15)
    score -= min(max(peak_util - 90, 0) * 1.0, 15)
    if circuit.status != CircuitStatus.ACTIVE:
        score = min(score, 50)
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
    )
