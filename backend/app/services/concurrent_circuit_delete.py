"""Background circuit record deletion — avoids blocking HTTP on large telemetry purges."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.core.database import SessionLocal
from app.services import circuit_delete_service

logger = logging.getLogger(__name__)

_bg_pool: ThreadPoolExecutor | None = None


def _background_pool() -> ThreadPoolExecutor:
    global _bg_pool
    if _bg_pool is None:
        workers = max(1, int(getattr(settings, "provision_max_concurrency", 4) or 4))
        _bg_pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="circuit-delete-bg")
    return _bg_pool


def schedule_circuit_delete(circuit_id: int) -> None:
    """Fire-and-forget permanent circuit record deletion."""

    def _run() -> None:
        db = SessionLocal()
        try:
            circuit_delete_service.delete_circuit_by_id(db, circuit_id)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("background circuit delete failed for id=%s", circuit_id)
        finally:
            db.close()

    _background_pool().submit(_run)
