"""Background scheduler for autonomous operations.

Periodically collects SNMP telemetry, rotates on-demand circuit probes for QoS
metrics, re-evaluates SLA/capacity alarms, and refreshes live-network inventory.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.circuit import Circuit
from app.models.enums import CircuitStatus
from app.models.link import Link
from app.services import alarm_service, config_learn, link_monitor, platform_settings, telemetry_service
from app.controller import bgp_peering, ha

logger = logging.getLogger("bugis.scheduler")

_task: asyncio.Task | None = None
_probe_cursor = 0
_last_learn_monotonic = 0.0
_state: dict = {
    "running": False,
    "ticks": 0,
    "last_tick": None,
    "last_samples": 0,
    "last_probes": 0,
    "last_learn": None,
    "last_learn_devices": 0,
    "last_learn_conflicts": 0,
    "interval": settings.scheduler_interval_seconds,
}


def _probe_one_circuit(db, circuits: list[Circuit]) -> bool:
    """Rotate through active circuits and run a live path probe (QoS metrics)."""
    global _probe_cursor
    if settings.dry_run or not circuits:
        return False
    circuit = circuits[_probe_cursor % len(circuits)]
    _probe_cursor += 1
    try:
        from app.services.circuit_probe.runner import probe_circuit

        probe_circuit(db, circuit)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("scheduled probe failed for %s: %s", circuit.code, exc)
        return False


def _maybe_learn_inventory(db) -> dict | None:
    """Run scheduled auto-learn when the configured interval has elapsed."""
    global _last_learn_monotonic
    plat = platform_settings.get_or_create(db)
    if not plat.auto_learn_enabled:
        return None
    interval = max(30, int(plat.auto_learn_interval_seconds or 60))
    now = time.monotonic()
    if _last_learn_monotonic and (now - _last_learn_monotonic) < interval:
        return None
    summary = config_learn.scheduled_learn_all_online(db, created_by="scheduler")
    _last_learn_monotonic = now
    _state["last_learn"] = datetime.now(timezone.utc).isoformat()
    _state["last_learn_devices"] = summary.get("devices", 0)
    _state["last_learn_conflicts"] = summary.get("conflicts", 0)
    return summary


def _tick() -> int:
    db = SessionLocal()
    try:
        learn_summary = _maybe_learn_inventory(db)
        if learn_summary and not learn_summary.get("skipped"):
            logger.info(
                "scheduled learn: %s/%s devices, %s conflicts",
                learn_summary.get("success"),
                learn_summary.get("devices"),
                learn_summary.get("conflicts"),
            )
        circuits = db.execute(
            select(Circuit).where(Circuit.status == CircuitStatus.ACTIVE)
        ).scalars().all()
        collected = 0
        for c in circuits:
            if telemetry_service.collect_circuit_sample(
                db, c, interval_sec=float(_state["interval"])
            ):
                collected += 1
        probed = _probe_one_circuit(db, circuits)
        db.flush()
        for c in circuits:
            health = telemetry_service.compute_health(db, c)
            alarm_service.evaluate_circuit_health(db, c, health)
            alarm_service.evaluate_circuit_availability(db, c)
        link_monitor.sync_all_link_capacity(db)
        link_samples = link_monitor.sample_all_links(
            db, interval_sec=float(_state["interval"])
        )
        links = db.execute(select(Link)).scalars().all()
        for link in links:
            lh = link_monitor.compute_link_health(db, link)
            alarm_service.evaluate_link_health(db, link, lh)
        bgp_peering.sync_sessions(db)
        ha.heartbeat(db)
        db.commit()
        _state["last_probes"] = 1 if probed else 0
        return collected
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


def set_interval(seconds: int) -> None:
    _state["interval"] = seconds


def status() -> dict:
    return {**_state, "enabled": settings.scheduler_enabled}


def run_once() -> int:
    """Synchronously run a single tick (for manual trigger / tests)."""
    count = _tick()
    _state["ticks"] += 1
    _state["last_samples"] = count
    _state["last_tick"] = datetime.now(timezone.utc).isoformat()
    return count
