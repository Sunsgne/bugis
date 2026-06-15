"""Circuit availability: interruption / flash detection and SLA uptime."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.availability import CircuitAvailabilityEvent
from app.models.circuit import Circuit
from app.models.telemetry import TelemetrySample

FLASH_MAX_SEC = 300
FLAP_WINDOW_MIN = 15
FLAP_COUNT_THRESHOLD = 3


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _open_event(db: Session, circuit_id: int) -> CircuitAvailabilityEvent | None:
    return db.execute(
        select(CircuitAvailabilityEvent).where(
            CircuitAvailabilityEvent.circuit_id == circuit_id,
            CircuitAvailabilityEvent.ended_at.is_(None),
        )
    ).scalar_one_or_none()


def process_tunnel_state(
    db: Session,
    circuit: Circuit,
    *,
    tunnel_up: bool,
    source: str = "tunnel_state",
    at: datetime | None = None,
) -> CircuitAvailabilityEvent | None:
    """Open/close availability events based on tunnel up/down transitions."""
    now = at or _utcnow()
    open_ev = _open_event(db, circuit.id)

    if not tunnel_up:
        if open_ev:
            return open_ev
        ev = CircuitAvailabilityEvent(
            circuit_id=circuit.id,
            kind="interruption",
            started_at=now,
            source=source,
            detail=f"专线 {circuit.code} 检测到链路中断",
        )
        db.add(ev)
        db.flush()
        return ev

    if open_ev:
        ended = now
        if open_ev.started_at.tzinfo is None:
            started = open_ev.started_at.replace(tzinfo=timezone.utc)
        else:
            started = open_ev.started_at
        duration = max((ended - started).total_seconds(), 0.0)
        open_ev.ended_at = ended
        open_ev.duration_sec = round(duration, 1)
        if duration <= FLASH_MAX_SEC:
            open_ev.kind = "flash"
            open_ev.detail = f"闪断 {round(duration, 1)}s"
        else:
            open_ev.detail = f"中断 {round(duration / 60, 1)} 分钟"
        db.flush()
        return open_ev
    return None


def flap_count(db: Session, circuit_id: int, window_min: int = FLAP_WINDOW_MIN) -> int:
    since = _utcnow() - timedelta(minutes=window_min)
    rows = db.execute(
        select(CircuitAvailabilityEvent).where(
            CircuitAvailabilityEvent.circuit_id == circuit_id,
            CircuitAvailabilityEvent.kind == "flash",
            CircuitAvailabilityEvent.started_at >= since,
        )
    ).scalars().all()
    return len(rows)


def compute_availability(
    db: Session,
    circuit: Circuit,
    *,
    hours: int = 24,
) -> dict:
    """Summarize uptime, interruptions and recent events for a circuit."""
    hours = max(1, min(hours, 24 * 30))
    since = _utcnow() - timedelta(hours=hours)
    window_sec = hours * 3600.0

    events = db.execute(
        select(CircuitAvailabilityEvent)
        .where(
            CircuitAvailabilityEvent.circuit_id == circuit.id,
            CircuitAvailabilityEvent.started_at >= since,
        )
        .order_by(CircuitAvailabilityEvent.started_at.desc())
        .limit(50)
    ).scalars().all()

    samples = db.execute(
        select(TelemetrySample)
        .where(
            TelemetrySample.circuit_id == circuit.id,
            TelemetrySample.created_at >= since,
        )
        .order_by(TelemetrySample.id.asc())
    ).scalars().all()

    downtime = 0.0
    for ev in events:
        if ev.duration_sec is not None:
            downtime += ev.duration_sec
        elif ev.ended_at is None:
            started = ev.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            downtime += max((_utcnow() - started).total_seconds(), 0.0)

    uptime_pct = round(max(0.0, (window_sec - downtime) / window_sec * 100), 3)
    interruption_count = sum(1 for e in events if e.kind == "interruption")
    flash_count = sum(1 for e in events if e.kind == "flash")
    avg_lat = (
        round(sum(s.latency_ms for s in samples) / len(samples), 2) if samples else 0.0
    )

    return {
        "circuit_id": circuit.id,
        "circuit_code": circuit.code,
        "hours": hours,
        "uptime_pct": uptime_pct,
        "interruption_count": interruption_count,
        "flash_count": flash_count,
        "total_downtime_sec": round(downtime, 1),
        "avg_latency_ms": avg_lat,
        "flap_count": flap_count(db, circuit.id),
        "events": events,
    }
