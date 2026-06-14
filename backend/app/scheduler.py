"""Background scheduler for autonomous operations.

Periodically (a) generates telemetry samples for active circuits and
(b) re-evaluates SLA/capacity alarms, so dashboards, the SSE stream and the
alarm center stay live without manual triggering — closer to 7x24 operations.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.circuit import Circuit
from app.models.enums import CircuitStatus
from app.services import alarm_service, telemetry_service

logger = logging.getLogger("bugis.scheduler")

_task: asyncio.Task | None = None
_state: dict = {
    "running": False,
    "ticks": 0,
    "last_tick": None,
    "last_samples": 0,
    "interval": settings.scheduler_interval_seconds,
}


def _tick() -> int:
    db = SessionLocal()
    try:
        circuits = db.execute(
            select(Circuit).where(Circuit.status == CircuitStatus.ACTIVE)
        ).scalars().all()
        for c in circuits:
            telemetry_service.simulate_circuit_sample(db, c)
        db.flush()
        for c in circuits:
            health = telemetry_service.compute_health(db, c)
            alarm_service.evaluate_circuit_health(db, c, health)
        db.commit()
        return len(circuits)
    finally:
        db.close()


async def _run() -> None:
    _state["running"] = True
    logger.info("scheduler started (interval=%ss)", _state["interval"])
    try:
        while True:
            await asyncio.sleep(_state["interval"])
            try:
                count = await asyncio.to_thread(_tick)
                _state["ticks"] += 1
                _state["last_samples"] = count
                _state["last_tick"] = datetime.now(timezone.utc).isoformat()
            except Exception as exc:  # noqa: BLE001
                logger.exception("scheduler tick failed: %s", exc)
    except asyncio.CancelledError:  # pragma: no cover
        pass
    finally:
        _state["running"] = False
        logger.info("scheduler stopped")


def start() -> None:
    global _task
    if not settings.scheduler_enabled:
        return
    if _task and not _task.done():
        return
    _state["interval"] = settings.scheduler_interval_seconds
    _task = asyncio.create_task(_run())


async def stop() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:  # pragma: no cover
            pass
    _task = None


def status() -> dict:
    return {**_state, "enabled": settings.scheduler_enabled}


def run_once() -> int:
    """Synchronously run a single tick (for manual trigger / tests)."""
    count = _tick()
    _state["ticks"] += 1
    _state["last_samples"] = count
    _state["last_tick"] = datetime.now(timezone.utc).isoformat()
    return count
