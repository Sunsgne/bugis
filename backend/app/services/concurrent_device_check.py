"""Parallel device reachability + S-VID checks — each worker uses its own DB session."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.config import settings
from app.core.database import SessionLocal
from app.services import device_check_service

logger = logging.getLogger(__name__)

_bg_pool: ThreadPoolExecutor | None = None


def _background_pool() -> ThreadPoolExecutor:
    global _bg_pool
    if _bg_pool is None:
        workers = max(1, int(getattr(settings, "provision_max_concurrency", 4) or 4))
        _bg_pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="device-check-bg")
    return _bg_pool


def check_devices_parallel(
    device_ids: list[int],
    *,
    max_workers: int | None = None,
) -> list[dict]:
    """Run reachability + S-VID scan for multiple devices concurrently."""
    unique = list(dict.fromkeys(device_ids))
    if not unique:
        return []

    order = {did: idx for idx, did in enumerate(unique)}

    def _check_one(device_id: int) -> dict:
        db = SessionLocal()
        try:
            result = device_check_service.run_device_check(db, device_id)
            db.commit()
            return result
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("device check failed for id=%s", device_id)
            return {"device_id": device_id, "success": False, "error": str(exc)}
        finally:
            db.close()

    if len(unique) == 1:
        return [_check_one(unique[0])]

    workers = min(max(1, max_workers or 4), len(unique))
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_check_one, did) for did in unique]
        for fut in as_completed(futures):
            results.append(fut.result())
    results.sort(key=lambda r: order.get(r.get("device_id"), 999))
    return results


def schedule_device_checks(
    device_ids: list[int],
    *,
    max_workers: int | None = None,
) -> None:
    """Fire-and-forget reachability + S-VID checks."""
    unique = list(dict.fromkeys(device_ids))
    if not unique:
        return
    workers = max_workers
    if workers is None:
        workers = max(1, int(getattr(settings, "provision_max_concurrency", 4) or 4))

    def _run() -> None:
        try:
            check_devices_parallel(unique, max_workers=workers)
        except Exception:
            logger.exception("background device check failed for %s device(s)", len(unique))

    _background_pool().submit(_run)


def schedule_device_check(device_id: int) -> None:
    schedule_device_checks([device_id])
