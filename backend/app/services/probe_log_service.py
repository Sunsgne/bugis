"""Persist circuit probe runs for frontend history display."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit
from app.models.circuit_probe_log import CircuitProbeLog


def save_probe_log(db: Session, circuit: Circuit, result: dict) -> CircuitProbeLog:
    row = CircuitProbeLog(
        circuit_id=circuit.id,
        mode=str(result.get("mode") or "unknown"),
        probe_method=result.get("probe_method"),
        reachable=bool(result.get("reachable")),
        rtt_ms=result.get("rtt_ms"),
        jitter_ms=result.get("jitter_ms"),
        packet_loss_pct=result.get("packet_loss_pct"),
        path_mode=result.get("path_mode"),
        result_json=result,
    )
    db.add(row)
    db.flush()
    return row


def latest_probe_log(db: Session, circuit_id: int) -> CircuitProbeLog | None:
    return db.execute(
        select(CircuitProbeLog)
        .where(CircuitProbeLog.circuit_id == circuit_id)
        .order_by(CircuitProbeLog.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def list_probe_logs(db: Session, circuit_id: int, *, limit: int = 20) -> list[CircuitProbeLog]:
    limit = max(1, min(limit, 100))
    return list(db.execute(
        select(CircuitProbeLog)
        .where(CircuitProbeLog.circuit_id == circuit_id)
        .order_by(CircuitProbeLog.id.desc())
        .limit(limit)
    ).scalars().all())
