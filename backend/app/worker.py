"""Background provisioning worker.

Executes provision / teardown work orders off the HTTP request path so a burst
of concurrent operators never exhausts the request thread pool (the platform
otherwise runs ``orchestrator.execute`` — which pushes synchronously over
SSH/NETCONF — inline in the request, serializing under load).

Model
-----
* A work order queued for the worker is marked ``status=scheduled``.
* The worker dispatches each scheduled work order onto a thread (device I/O is
  blocking) and runs up to ``settings.provision_max_concurrency`` in parallel.
* A periodic reconcile loop also picks up any ``scheduled`` work orders that
  were never dispatched (e.g. enqueued just before a restart), so nothing is
  stranded.
* ``process_pending`` provides a synchronous drain used by tests / manual
  triggers when no event loop is running.

The worker is intentionally simple and single-process (the production stack is
single-node). It never changes default behavior unless ``async_provisioning``
is enabled; the provision endpoint only enqueues when that flag is on.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.enums import WorkOrderStatus
from app.models.workorder import WorkOrder
from app.services import orchestrator

logger = logging.getLogger("bugis.worker")

_loop: asyncio.AbstractEventLoop | None = None
_reconcile_task: asyncio.Task | None = None
_dispatch_lock: asyncio.Lock | None = None
_inflight: set[int] = set()
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


# --- enqueue -------------------------------------------------------------

def enqueue(wo_id: int) -> None:
    """Hand a scheduled work order to the running worker loop (best-effort).

    Safe to call from a request (sync) thread: it schedules a dispatch on the
    worker's event loop. If no loop is running (e.g. tests), this is a no-op and
    the work order will be drained by ``process_pending`` / the reconcile loop.
    """
    loop = _loop
    if loop is None or loop.is_closed():
        return
    try:
        asyncio.run_coroutine_threadsafe(_dispatch_available(), loop)
    except RuntimeError:  # pragma: no cover - loop shutting down
        pass


# --- core execution ------------------------------------------------------

def _run_one(wo_id: int) -> WorkOrderStatus | None:
    """Execute a single scheduled work order in a fresh DB session."""
    db = SessionLocal()
    try:
        wo = db.get(WorkOrder, wo_id)
        if not wo or wo.status != WorkOrderStatus.SCHEDULED:
            return None
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
        # A slot freed up — pull in any remaining queued work.
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


def start() -> None:
    global _loop, _reconcile_task, _dispatch_lock
    _loop = asyncio.get_event_loop()
    _dispatch_lock = asyncio.Lock()
    if _reconcile_task and not _reconcile_task.done():
        return
    _reconcile_task = asyncio.create_task(_reconcile_loop())


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
    """Synchronously execute all (or up to ``limit``) scheduled work orders.

    Used by tests and a manual admin trigger when no worker loop is running.
    """
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
        "enabled": bool(getattr(settings, "async_provisioning", False)),
        "max_concurrency": _max_concurrency(),
        "pending": pending_count(),
    }
