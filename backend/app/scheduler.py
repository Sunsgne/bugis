"""Background scheduler for autonomous operations.

Periodically collects SNMP telemetry, rotates on-demand circuit probes for QoS
metrics, re-evaluates SLA/capacity alarms, and refreshes live-network inventory.

Scheduled config pull (auto-learn) uses ``auto_learn_interval_seconds`` from
platform settings and persists its schedule via ``device_learn_runs`` so restarts
do not reset the interval. Learn runs in a background thread so SNMP ticks are
not blocked for minutes while SSH/NETCONF fetches complete.

At ~10k active circuits, SNMP and probe work is batched per tick (round-robin)
so each tick stays bounded; alarm evaluation runs only for circuits touched
in that tick.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.circuit import Circuit
from app.models.device_learn_run import DeviceLearnRun
from app.models.enums import CircuitStatus
from app.models.link import Link
from app.services import alarm_service, config_learn, health_snapshot_service, link_monitor, platform_settings, snmp_discovery_service, telemetry_service
from app.controller import bgp_peering, ha

logger = logging.getLogger("bugis.scheduler")

_task: asyncio.Task | None = None
_learn_task: asyncio.Task | None = None
_snmp_discover_task: asyncio.Task | None = None
_learn_lock = threading.Lock()
_snmp_discover_lock = threading.Lock()
_tick_lock = threading.Lock()
_probe_cursor = 0
_collect_cursor = 0
_state: dict = {
    "running": False,
    "ticks": 0,
    "last_tick": None,
    "last_samples": 0,
    "last_probes": 0,
    "last_learn": None,
    "last_learn_devices": 0,
    "last_learn_conflicts": 0,
    "learn_running": False,
    "snmp_discover_running": False,
    "tick_running": False,
    "tick_skipped": 0,
    "last_snmp_discover": None,
    "last_snmp_discover_devices": 0,
    "interval": settings.scheduler_interval_seconds,
    "collect_batch_size": settings.telemetry_collect_batch_size,
    "probe_batch_size": settings.telemetry_probe_batch_size,
}


def _last_scheduled_learn_at(db) -> datetime | None:
    """Latest scheduler-driven learn timestamp (persisted, survives restarts)."""
    return db.execute(
        select(func.max(DeviceLearnRun.created_at)).where(
            DeviceLearnRun.created_by == "scheduler"
        )
    ).scalar_one_or_none()


def _learn_interval_elapsed(db, interval: int) -> bool:
    last = _last_scheduled_learn_at(db)
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - last).total_seconds()
    return elapsed >= interval


def _auto_learn_interval_seconds(db) -> int:
    plat = platform_settings.get_or_create(db)
    return max(30, int(plat.auto_learn_interval_seconds or 60))


def _is_scheduled_learn_due(db) -> bool:
    plat = platform_settings.get_or_create(db)
    if not plat.auto_learn_enabled:
        return False
    return _learn_interval_elapsed(db, _auto_learn_interval_seconds(db))


def _update_learn_state(summary: dict) -> None:
    _state["last_learn"] = datetime.now(timezone.utc).isoformat()
    _state["last_learn_devices"] = summary.get("devices", 0)
    _state["last_learn_conflicts"] = summary.get("conflicts", 0)


def _execute_scheduled_learn() -> dict | None:
    """Run one scheduled learn cycle (blocking — intended for background thread)."""
    if not _learn_lock.acquire(blocking=False):
        return None
    _state["learn_running"] = True
    db = SessionLocal()
    try:
        if not _is_scheduled_learn_due(db):
            return None
        summary = config_learn.scheduled_learn_all_online(db, created_by="scheduler")
        if summary.get("skipped"):
            return summary
        db.commit()
        _update_learn_state(summary)
        return summary
    except Exception:
        db.rollback()
        raise
    finally:
        _state["learn_running"] = False
        db.close()
        _learn_lock.release()


def _try_scheduled_learn_sync() -> dict | None:
    """Run scheduled learn synchronously when due (manual tick / tests)."""
    try:
        summary = _execute_scheduled_learn()
        if summary and not summary.get("skipped"):
            logger.info(
                "scheduled learn: %s/%s devices, %s conflicts",
                summary.get("success"),
                summary.get("devices"),
                summary.get("conflicts"),
            )
        return summary
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduled learn failed: %s", exc)
        return None


async def _maybe_start_learn_task() -> None:
    global _learn_task
    if _state.get("learn_running"):
        return
    if _learn_task is not None and not _learn_task.done():
        return

    def _due_check() -> bool:
        db = SessionLocal()
        try:
            return _is_scheduled_learn_due(db)
        finally:
            db.close()

    if not await asyncio.to_thread(_due_check):
        return

    async def _job() -> None:
        try:
            await asyncio.to_thread(_try_scheduled_learn_sync)
        except Exception as exc:  # noqa: BLE001
            logger.exception("scheduled learn task failed: %s", exc)

    _learn_task = asyncio.create_task(_job())


def _update_snmp_discover_state(summary: dict) -> None:
    _state["last_snmp_discover"] = datetime.now(timezone.utc).isoformat()
    _state["last_snmp_discover_devices"] = summary.get("devices", 0)


def _execute_scheduled_snmp_discover() -> dict | None:
    """Run one scheduled SNMP discovery sweep (blocking — background thread)."""
    if not _snmp_discover_lock.acquire(blocking=False):
        return None
    _state["snmp_discover_running"] = True
    db = SessionLocal()
    try:
        if not snmp_discovery_service.is_scheduled_discover_due(db):
            return None
        summary = snmp_discovery_service.scheduled_discover_all_online(db, created_by="scheduler")
        if summary.get("skipped"):
            return summary
        db.commit()
        _update_snmp_discover_state(summary)
        return summary
    except Exception:
        db.rollback()
        raise
    finally:
        _state["snmp_discover_running"] = False
        db.close()
        _snmp_discover_lock.release()


def _try_scheduled_snmp_discover_sync() -> dict | None:
    try:
        summary = _execute_scheduled_snmp_discover()
        if summary and not summary.get("skipped"):
            logger.info(
                "scheduled SNMP discover: %s/%s devices ok, %s failed",
                summary.get("success"),
                summary.get("devices"),
                summary.get("failed"),
            )
        return summary
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduled SNMP discover failed: %s", exc)
        return None


async def _maybe_start_snmp_discover_task() -> None:
    global _snmp_discover_task
    if _state.get("snmp_discover_running"):
        return
    if _snmp_discover_task is not None and not _snmp_discover_task.done():
        return

    def _due_check() -> bool:
        db = SessionLocal()
        try:
            return snmp_discovery_service.is_scheduled_discover_due(db)
        finally:
            db.close()

    if not await asyncio.to_thread(_due_check):
        return

    async def _job() -> None:
        try:
            await asyncio.to_thread(_try_scheduled_snmp_discover_sync)
        except Exception as exc:  # noqa: BLE001
            logger.exception("scheduled SNMP discover task failed: %s", exc)

    _snmp_discover_task = asyncio.create_task(_job())


def _probe_one_circuit(db, circuits: list[Circuit]) -> tuple[int, set[int]]:
    """Rotate through active circuits and run live path probes (QoS metrics)."""
    global _probe_cursor
    touched: set[int] = set()
    if settings.dry_run or not circuits:
        return 0, touched
    probeable = [c for c in circuits if c.latency_probe_enabled]
    if not probeable:
        return 0, touched
    batch = max(1, min(settings.telemetry_probe_batch_size, len(probeable)))
    probed = 0
    from app.services.circuit_probe.runner import probe_circuit

    for _ in range(batch):
        circuit = probeable[_probe_cursor % len(probeable)]
        _probe_cursor += 1
        try:
            probe_circuit(db, circuit)
            probed += 1
            touched.add(circuit.id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("scheduled probe failed for %s: %s", circuit.code, exc)
    return probed, touched


def _collect_circuit_batch(
    db,
    circuits: list[Circuit],
    *,
    interval_sec: float,
) -> tuple[int, set[int]]:
    """SNMP telemetry for a round-robin batch of active circuits."""
    global _collect_cursor
    touched: set[int] = set()
    if not circuits:
        return 0, touched
    batch = max(1, min(settings.telemetry_collect_batch_size, len(circuits)))
    collected = 0
    for _ in range(batch):
        circuit = circuits[_collect_cursor % len(circuits)]
        _collect_cursor += 1
        if telemetry_service.collect_circuit_sample(
            db, circuit, interval_sec=interval_sec
        ):
            collected += 1
        touched.add(circuit.id)
    return collected, touched


def _tick(*, include_learn: bool = False) -> int:
    if include_learn:
        _try_scheduled_learn_sync()

    if not _tick_lock.acquire(blocking=False):
        _state["tick_skipped"] = int(_state.get("tick_skipped") or 0) + 1
        return 0

    _state["tick_running"] = True
    try:
        return _tick_body()
    finally:
        _state["tick_running"] = False
        _tick_lock.release()


def _tick_body() -> int:
    collected = 0
    touched_ids: set[int] = set()
    probed = 0

    db = SessionLocal()
    try:
        circuits = db.execute(
            select(Circuit).where(Circuit.status == CircuitStatus.ACTIVE)
        ).scalars().all()
        collected, collect_touched = _collect_circuit_batch(
            db,
            circuits,
            interval_sec=float(_state["interval"]),
        )
        probed, probe_touched = _probe_one_circuit(db, circuits)
        touched_ids = collect_touched | probe_touched
        circuit_by_id = {c.id: c for c in circuits}
        for cid in touched_ids:
            c = circuit_by_id.get(cid)
            if not c:
                continue
            health = telemetry_service.compute_health_for_alarms(db, c)
            health_snapshot_service.upsert_from_health(db, c.id, health)
            health_snapshot_service.invalidate_circuit(c)
            alarm_service.evaluate_circuit_health(db, c, health)
            alarm_service.evaluate_circuit_availability(db, c)
        db.commit()
    finally:
        db.close()

    db = SessionLocal()
    try:
        link_monitor.sync_all_link_capacity(db)
        db.commit()
    finally:
        db.close()

    # Per-link sessions — SNMP can be slow; must not block the pool.
    link_monitor.sample_all_links(interval_sec=float(_state["interval"]))

    db = SessionLocal()
    try:
        links = db.execute(select(Link)).scalars().all()
        for link in links:
            lh = link_monitor.compute_link_health(db, link)
            alarm_service.evaluate_link_health(db, link, lh)
        bgp_peering.sync_sessions(db)
        ha.heartbeat(db)
        db.commit()
    finally:
        db.close()

    _state["last_probes"] = probed
    return collected


async def _run() -> None:
    _state["running"] = True
    logger.info("scheduler started (interval=%ss)", _state["interval"])
    try:
        while True:
            await asyncio.sleep(_state["interval"])
            try:
                await _maybe_start_learn_task()
                await _maybe_start_snmp_discover_task()
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
    _state["collect_batch_size"] = settings.telemetry_collect_batch_size
    _state["probe_batch_size"] = settings.telemetry_probe_batch_size
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
    base = {**_state, "enabled": settings.scheduler_enabled}
    db = SessionLocal()
    try:
        plat = platform_settings.get_or_create(db)
        interval = _auto_learn_interval_seconds(db)
        last = _last_scheduled_learn_at(db)
        if last is not None:
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            base["last_learn"] = last.isoformat()
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            if plat.auto_learn_enabled:
                remaining = max(0, int(interval - elapsed))
                base["next_learn_in_seconds"] = remaining
                base["next_learn_at"] = (
                    datetime.now(timezone.utc) + timedelta(seconds=remaining)
                ).isoformat()
            else:
                base["next_learn_in_seconds"] = None
        else:
            base["next_learn_in_seconds"] = 0 if plat.auto_learn_enabled else None
        base["auto_learn_enabled"] = plat.auto_learn_enabled
        base["auto_learn_interval_seconds"] = interval
        snmp_interval = snmp_discovery_service.snmp_discover_interval_seconds(db)
        last_snmp = getattr(plat, "last_snmp_discover_at", None)
        base["snmp_discover_enabled"] = snmp_discovery_service.snmp_discover_enabled(db)
        base["snmp_discover_interval_seconds"] = snmp_interval
        if last_snmp is not None:
            if last_snmp.tzinfo is None:
                last_snmp = last_snmp.replace(tzinfo=timezone.utc)
            base["last_snmp_discover"] = last_snmp.isoformat()
            elapsed_snmp = (datetime.now(timezone.utc) - last_snmp).total_seconds()
            if base["snmp_discover_enabled"]:
                remaining_snmp = max(0, int(snmp_interval - elapsed_snmp))
                base["next_snmp_discover_in_seconds"] = remaining_snmp
                base["next_snmp_discover_at"] = (
                    datetime.now(timezone.utc) + timedelta(seconds=remaining_snmp)
                ).isoformat()
            else:
                base["next_snmp_discover_in_seconds"] = None
        else:
            base["next_snmp_discover_in_seconds"] = (
                0 if base["snmp_discover_enabled"] else None
            )
    finally:
        db.close()
    return base


def run_once() -> int:
    """Synchronously run a single tick (for manual trigger / tests)."""
    count = _tick(include_learn=True)
    _state["ticks"] += 1
    _state["last_samples"] = count
    _state["last_tick"] = datetime.now(timezone.utc).isoformat()
    return count
