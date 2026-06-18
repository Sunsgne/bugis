"""Parallel device inventory scans — each worker uses its own DB session."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.database import SessionLocal
from app.models.device import Device
from app.services import port_inventory


def scan_devices_parallel(
    device_ids: list[int],
    *,
    include_legacy: bool = False,
    max_workers: int = 4,
) -> None:
    """Refresh S-VID inventory for multiple devices concurrently."""
    unique = list(dict.fromkeys(device_ids))
    if not unique:
        return

    def _scan_one(device_id: int) -> None:
        db = SessionLocal()
        try:
            device = db.get(Device, device_id)
            if device:
                port_inventory.scan_device(db, device, include_legacy=include_legacy)
                db.commit()
        finally:
            db.close()

    if len(unique) == 1:
        _scan_one(unique[0])
        return

    workers = min(max_workers, len(unique))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_scan_one, did) for did in unique]
        for fut in as_completed(futures):
            fut.result()
