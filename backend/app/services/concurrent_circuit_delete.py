"""Background circuit record deletion — avoids blocking HTTP on large telemetry purges."""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from app.core.config import settings
from app.core.database import SessionLocal
from app.services import circuit_delete_service

logger = logging.getLogger(__name__)

DeleteJobStatus = Literal["pending", "running", "succeeded", "failed"]

_bg_pool: ThreadPoolExecutor | None = None
_delete_jobs: dict[int, dict] = {}
_jobs_lock = threading.Lock()


def _background_pool() -> ThreadPoolExecutor:
    global _bg_pool
    if _bg_pool is None:
        workers = max(1, int(getattr(settings, "provision_max_concurrency", 4) or 4))
        _bg_pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="circuit-delete-bg")
    return _bg_pool


def get_delete_job(circuit_id: int) -> dict | None:
    with _jobs_lock:
        job = _delete_jobs.get(circuit_id)
        return dict(job) if job else None


def _set_delete_job(circuit_id: int, **fields) -> None:
    with _jobs_lock:
        current = dict(_delete_jobs.get(circuit_id) or {})
        current.update(fields)
        _delete_jobs[circuit_id] = current


def schedule_circuit_delete(circuit_id: int, *, circuit_code: str | None = None) -> None:
    """Fire-and-forget permanent circuit record deletion."""
    _set_delete_job(
        circuit_id,
        status="pending",
        circuit_code=circuit_code,
        error=None,
    )

    def _run() -> None:
        _set_delete_job(circuit_id, status="running", error=None)
        db = SessionLocal()
        try:
            circuit_delete_service.delete_circuit_by_id(db, circuit_id)
            db.commit()
            _set_delete_job(circuit_id, status="succeeded", error=None)
        except Exception as exc:
            db.rollback()
            logger.exception("background circuit delete failed for id=%s", circuit_id)
            _set_delete_job(circuit_id, status="failed", error=str(exc))
        finally:
            db.close()

    _background_pool().submit(_run)
