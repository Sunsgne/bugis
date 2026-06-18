"""Persist and read precomputed circuit health for portal-scale queries."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import redis_client
from app.core.config import get_settings
from app.models.circuit import Circuit
from app.models.enums import CircuitStatus
from app.models.health_snapshot import CircuitHealthSnapshot
from app.schemas.telemetry import CircuitHealth


def _cache_prefix() -> str:
    return get_settings().redis_key_prefix.rstrip(":")


def cache_key_health(circuit_id: int) -> str:
    return f"{_cache_prefix()}:health:{circuit_id}"


def cache_key_portal_dashboard(tenant_id: int) -> str:
    return f"{_cache_prefix()}:portal:dashboard:{tenant_id}"


def cache_key_traffic(circuit_id: int, hours: int) -> str:
    return f"{_cache_prefix()}:traffic:{circuit_id}:h{hours}"


def cache_key_overview(hours: int) -> str:
    return f"{_cache_prefix()}:overview:traffic:h{hours}"


def upsert_from_health(db: Session, circuit_id: int, health: CircuitHealth) -> None:
    now = datetime.now(timezone.utc)
    row = db.get(CircuitHealthSnapshot, circuit_id)
    if row is None:
        row = CircuitHealthSnapshot(circuit_id=circuit_id, updated_at=now)
        db.add(row)
    row.health_score = health.health_score
    row.avg_latency_ms = health.avg_latency_ms
    row.avg_jitter_ms = health.avg_jitter_ms
    row.avg_packet_loss_pct = health.avg_packet_loss_pct
    row.avg_utilization_pct = health.avg_utilization_pct
    row.peak_utilization_pct = health.peak_utilization_pct
    row.tunnel_down = health.tunnel_down
    row.qos_samples = health.qos_samples
    row.samples = health.samples
    row.updated_at = now
    db.flush()


def snapshot_to_health(circuit: Circuit, snap: CircuitHealthSnapshot) -> CircuitHealth:
    return CircuitHealth(
        circuit_id=circuit.id,
        circuit_code=circuit.code,
        status=circuit.status.value,
        sla_target=circuit.sla_target,
        avg_latency_ms=round(snap.avg_latency_ms, 2),
        avg_jitter_ms=round(snap.avg_jitter_ms, 2),
        avg_packet_loss_pct=round(snap.avg_packet_loss_pct, 3),
        avg_utilization_pct=round(snap.avg_utilization_pct, 2),
        peak_utilization_pct=round(snap.peak_utilization_pct, 2),
        bandwidth_mbps=circuit.bandwidth_mbps,
        samples=snap.samples,
        qos_samples=snap.qos_samples,
        health_score=snap.health_score,
        tunnel_down=snap.tunnel_down,
        data_sources=[],
    )


def get_snapshot_health(db: Session, circuit: Circuit) -> CircuitHealth | None:
    snap = db.get(CircuitHealthSnapshot, circuit.id)
    if snap is None:
        return None
    return snapshot_to_health(circuit, snap)


def tenant_monitorable_stats(db: Session, tenant_id: int) -> tuple[float, int]:
    """Average health score and monitorable circuit count from snapshots."""
    row = db.execute(
        select(
            func.coalesce(func.avg(CircuitHealthSnapshot.health_score), 100.0),
            func.count(Circuit.id),
        )
        .select_from(Circuit)
        .outerjoin(
            CircuitHealthSnapshot,
            CircuitHealthSnapshot.circuit_id == Circuit.id,
        )
        .where(
            Circuit.tenant_id == tenant_id,
            Circuit.status.in_((CircuitStatus.ACTIVE, CircuitStatus.DEGRADED)),
        )
    ).one()
    avg_score = round(float(row[0] or 100.0), 1)
    monitorable = int(row[1] or 0)
    return avg_score, monitorable


def invalidate_circuit(circuit: Circuit) -> None:
    redis_client.cache_delete(cache_key_health(circuit.id))
    redis_client.cache_delete(cache_key_portal_dashboard(circuit.tenant_id))
    redis_client.cache_delete_prefix(f"{_cache_prefix()}:traffic:{circuit.id}:")
