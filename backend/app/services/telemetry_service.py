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
