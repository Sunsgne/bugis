"""Parallel SNMP interface discovery — each worker uses its own DB session."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.config import settings
from app.core.database import SessionLocal
from app.services import snmp_discover_service

logger = logging.getLogger(__name__)

_bg_pool: ThreadPoolExecutor | None = None


def _background_pool() -> ThreadPoolExecutor:
    global _bg_pool
    if _bg_pool is None:
        workers = max(1, int(getattr(settings, "provision_max_concurrency", 4) or 4))
        _bg_pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="snmp-discover-bg")
    return _bg_pool


def discover_devices_parallel(
    device_ids: list[int],
    *,
    max_workers: int | None = None,
) -> list[dict]:
    """Run SNMP interface discovery for multiple devices concurrently."""
    unique = list(dict.fromkeys(device_ids))
    if not unique:
        return []

    order = {did: idx for idx, did in enumerate(unique)}

    def _discover_one(device_id: int) -> dict:
        db = SessionLocal()
        try:
            result = snmp_discover_service.run_snmp_discover(db, device_id)
            db.commit()
            return result
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("SNMP discover failed for id=%s", device_id)
            return {"device_id": device_id, "success": False, "error": str(exc)}
        finally:
            db.close()

    if len(unique) == 1:
        return [_discover_one(unique[0])]

    workers = min(max(1, max_workers or 4), len(unique))
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_discover_one, did) for did in unique]
        for fut in as_completed(futures):
            results.append(fut.result())
    results.sort(key=lambda row: order.get(row.get("device_id"), 999))
    return results


def schedule_snmp_discovers(
    device_ids: list[int],
    *,
    max_workers: int | None = None,
) -> None:
    """Fire-and-forget SNMP interface discovery."""
    unique = list(dict.fromkeys(device_ids))
    if not unique:
        return
    workers = max_workers
    if workers is None:
        workers = max(1, int(getattr(settings, "provision_max_concurrency", 4) or 4))

    def _run() -> None:
        try:
            discover_devices_parallel(unique, max_workers=workers)
        except Exception:
            logger.exception("background SNMP discover failed for %s device(s)", len(unique))

    _background_pool().submit(_run)


def schedule_snmp_discover(device_id: int) -> None:
    schedule_snmp_discovers([device_id])
