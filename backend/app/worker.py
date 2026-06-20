"""Background provisioning worker.

Executes provision / teardown work orders off the HTTP request path so a burst
of concurrent operators never exhausts the request thread pool (the platform
otherwise runs ``orchestrator.execute`` — which pushes synchronously over
SSH/NETCONF — inline in the request, serializing under load).

Model
-----
* A work order queued for the worker is marked ``status=scheduled``.
* The worker atomically claims a work order (``scheduled`` -> ``running``) so
  HA multi-node deployments never execute the same job twice.
* Each scheduled work order runs on a thread (device I/O is blocking) with up to
  ``settings.provision_max_concurrency`` in parallel.
* A periodic reconcile loop also picks up any ``scheduled`` work orders that
  were never dispatched (e.g. enqueued just before a restart), so nothing is
  stranded.
* ``process_pending`` provides a synchronous drain used by tests / manual
  triggers when no event loop is running.

Disable on HA follower nodes via ``BUGIS_WORKER_ENABLED=false``.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone

from sqlalchemy import func, select, update

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.config_job import ConfigJob
from app.models.enums import CircuitStatus, WorkOrderStatus
from app.models.workorder import WorkOrder
from app.services import orchestrator

logger = logging.getLogger("bugis.worker")

_loop: asyncio.AbstractEventLoop | None = None
_reconcile_task: asyncio.Task | None = None
_dispatch_lock: asyncio.Lock | None = None
_inflight: set[int] = set()
_device_locks_guard = threading.Lock()
_device_locks: dict[int, threading.Lock] = {}
_state: dict = {
    "running": False,
    "processed": 0,
    "failed": 0,
    "inflight": 0,
    "last_run": None,
}


def _max_concurrency() -> int:
    try:
        return max(1, int(getattr(settings, "provision_max_concurrency", 4) or 4))
    except (TypeError, ValueError):
        return 4


def _device_ids_for_work_order(db, wo: WorkOrder) -> list[int]:
    ids: set[int] = set()
    circuit = wo.circuit
    if not circuit:
        return []
    for ep in circuit.endpoints:
        if ep.device_id:
            ids.add(ep.device_id)
    return sorted(ids)


def _acquire_device_locks(device_ids: list[int]) -> list[threading.Lock]:
    locks: list[threading.Lock] = []
    with _device_locks_guard:
        for did in device_ids:
            if did not in _device_locks:
                _device_locks[did] = threading.Lock()
            locks.append(_device_locks[did])
    for lock in locks:
        lock.acquire()
    return locks


def _release_device_locks(locks: list[threading.Lock]) -> None:
    for lock in reversed(locks):
        lock.release()


# --- enqueue -------------------------------------------------------------

def enqueue(wo_id: int) -> None:
    """Hand a scheduled work order to the running worker loop (best-effort)."""
    loop = _loop
    if loop is None or loop.is_closed():
        return
    try:
        asyncio.run_coroutine_threadsafe(_dispatch_available(), loop)
    except RuntimeError:  # pragma: no cover - loop shutting down
        pass


# --- core execution ------------------------------------------------------

def _claim_work_order(db, wo_id: int) -> WorkOrder | None:
    """Atomically claim a scheduled work order (HA-safe)."""
    result = db.execute(
        update(WorkOrder)
        .where(
            WorkOrder.id == wo_id,
            WorkOrder.status == WorkOrderStatus.SCHEDULED,
        )
        .values(status=WorkOrderStatus.RUNNING)
    )
    if not result.rowcount:
        db.rollback()
        return None
    db.commit()
    return db.get(WorkOrder, wo_id)


def _run_one(wo_id: int) -> WorkOrderStatus | None:
    """Execute a single scheduled work order in a fresh DB session."""
    db = SessionLocal()
    device_locks: list[threading.Lock] = []
    try:
        wo = _claim_work_order(db, wo_id)
        if not wo:
            return None
        device_locks = _acquire_device_locks(_device_ids_for_work_order(db, wo))
        actor = wo.requested_by or "worker"
        try:
            orchestrator.execute(db, wo, actor=actor)
        except Exception as exc:  # noqa: BLE001 - never let the worker crash
            wo.status = WorkOrderStatus.FAILED
            if wo.circuit:
                from app.models.enums import CircuitStatus

                wo.circuit.status = CircuitStatus.FAILED
            orchestrator._log(
                db, wo, f"后台执行异常：{exc}", level="error", actor=actor
            )
            logger.exception("work order %s failed in worker: %s", wo_id, exc)
        status = wo.status
        db.commit()
        return status
    finally:
        _release_device_locks(device_locks)
        db.close()


def _scheduled_ids(exclude: set[int]) -> list[int]:
    db = SessionLocal()
    try:
        rows = db.execute(
            select(WorkOrder.id)
            .where(WorkOrder.status == WorkOrderStatus.SCHEDULED)
            .order_by(WorkOrder.id.asc())
        ).scalars().all()
        return [r for r in rows if r not in exclude]
    finally:
        db.close()


def pending_count() -> int:
    db = SessionLocal()
    try:
        return int(
            db.scalar(
                select(func.count())
                .select_from(WorkOrder)
                .where(WorkOrder.status == WorkOrderStatus.SCHEDULED)
            )
            or 0
        )
    finally:
        db.close()


# --- async dispatch (event-loop bound) -----------------------------------

async def _dispatch_available() -> None:
    """Launch worker tasks for scheduled work orders, up to the concurrency cap."""
    if _dispatch_lock is None:
        return
    async with _dispatch_lock:
        while len(_inflight) < _max_concurrency():
            candidates = await asyncio.to_thread(_scheduled_ids, set(_inflight))
            if not candidates:
                break
            wo_id = candidates[0]
            _inflight.add(wo_id)
            _state["inflight"] = len(_inflight)
            assert _loop is not None
            _loop.create_task(_execute_async(wo_id))


async def _execute_async(wo_id: int) -> None:
    try:
        status = await asyncio.to_thread(_run_one, wo_id)
        _state["processed"] += 1
        if status == WorkOrderStatus.FAILED:
            _state["failed"] += 1
        _state["last_run"] = datetime.now(timezone.utc).isoformat()
    finally:
        _inflight.discard(wo_id)
        _state["inflight"] = len(_inflight)
        await _dispatch_available()


async def _reconcile_loop() -> None:
    _state["running"] = True
    interval = max(1, int(getattr(settings, "worker_poll_seconds", 5) or 5))
    logger.info("provisioning worker started (poll=%ss)", interval)
    try:
        while True:
            try:
                await _dispatch_available()
            except Exception as exc:  # noqa: BLE001
                logger.exception("worker reconcile failed: %s", exc)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:  # pragma: no cover
        pass
    finally:
        _state["running"] = False
        logger.info("provisioning worker stopped")


def recover_orphaned_running() -> list[int]:
    """Re-queue or fail work orders left RUNNING after a backend restart."""
    db = SessionLocal()
    requeue: list[int] = []
    try:
        orphans = db.execute(
            select(WorkOrder).where(WorkOrder.status == WorkOrderStatus.RUNNING)
        ).scalars().all()
        if not orphans:
            return requeue
        for wo in orphans:
            job_count = int(
                db.scalar(
                    select(func.count())
                    .select_from(ConfigJob)
                    .where(ConfigJob.work_order_id == wo.id)
                )
                or 0
            )
            if job_count == 0:
                wo.status = WorkOrderStatus.SCHEDULED
                orchestrator._log(
                    db,
                    wo,
                    "检测到进程重启导致执行中断，已重新加入开通队列",
                    actor="worker",
                )
                requeue.append(wo.id)
            else:
                wo.status = WorkOrderStatus.FAILED
                circuit = wo.circuit
                if circuit and circuit.status == CircuitStatus.PROVISIONING:
                    circuit.status = CircuitStatus.FAILED
                orchestrator._log(
                    db,
                    wo,
                    "检测到进程重启导致执行中断（已有部分配置作业），已标记失败",
                    level="error",
                    actor="worker",
                )
        db.commit()
        return requeue
    finally:
        db.close()


def start() -> None:
    global _loop, _reconcile_task, _dispatch_lock
    if not getattr(settings, "worker_enabled", True):
        logger.info("provisioning worker disabled (BUGIS_WORKER_ENABLED=false)")
        return
    requeued = recover_orphaned_running()
    if requeued:
        logger.info("recovered %s orphaned RUNNING work order(s)", len(requeued))
    _loop = asyncio.get_event_loop()
    _dispatch_lock = asyncio.Lock()
    if _reconcile_task and not _reconcile_task.done():
        return
    _reconcile_task = asyncio.create_task(_reconcile_loop())
    for wo_id in requeued:
        enqueue(wo_id)


async def stop() -> None:
    global _reconcile_task
    if _reconcile_task and not _reconcile_task.done():
        _reconcile_task.cancel()
        try:
            await _reconcile_task
        except asyncio.CancelledError:  # pragma: no cover
            pass
    _reconcile_task = None


# --- synchronous drain (tests / manual trigger) --------------------------

def process_pending(limit: int | None = None) -> int:
    """Synchronously execute all (or up to ``limit``) scheduled work orders."""
    processed = 0
    for wo_id in _scheduled_ids(set()):
        if limit is not None and processed >= limit:
            break
        status = _run_one(wo_id)
        if status is not None:
            processed += 1
            _state["processed"] += 1
            if status == WorkOrderStatus.FAILED:
                _state["failed"] += 1
    _state["last_run"] = datetime.now(timezone.utc).isoformat()
    return processed


def status() -> dict:
    return {
        **_state,
        "enabled": bool(getattr(settings, "async_provisioning", False))
        and bool(getattr(settings, "worker_enabled", True)),
        "max_concurrency": _max_concurrency(),
        "pending": pending_count(),
    }
