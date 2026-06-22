"""Parallel live-network config learning — each worker uses its own DB session."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.database import SessionLocal
from app.models.device import Device
from app.services import config_learn


def learn_devices_parallel(
    device_ids: list[int],
    *,
    created_by: str | None = None,
    discover_snmp: bool = True,
    max_workers: int = 4,
) -> dict:
    """Learn running-config for multiple devices concurrently (I/O-bound SSH/NETCONF)."""
    unique = list(dict.fromkeys(device_ids))
    if not unique:
        return {"total": 0, "success": 0, "failed": 0, "max_workers": 0, "results": []}

    order = {did: idx for idx, did in enumerate(unique)}

    def _learn_one(device_id: int) -> dict:
        db = SessionLocal()
        try:
            device = db.get(Device, device_id)
            if not device:
                return {"device_id": device_id, "success": False, "error": "not found"}
            result = config_learn.learn_device(
                db,
                device,
                created_by=created_by,
                discover_snmp=discover_snmp,
            )
            result.setdefault("device_id", device_id)
            db.commit()
            return result
        except Exception as exc:  # noqa: BLE001 — aggregate per-device errors for batch API
            db.rollback()
            return {"device_id": device_id, "success": False, "error": str(exc)}
        finally:
            db.close()

    if len(unique) == 1:
        results = [_learn_one(unique[0])]
        workers = 1
    else:
        workers = min(max(1, max_workers), len(unique))
        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_learn_one, did) for did in unique]
            for fut in as_completed(futures):
                results.append(fut.result())
        results.sort(
            key=lambda r: order.get(r.get("device_id"), 999),
        )

    ok = sum(1 for r in results if r.get("success"))
    return {
        "total": len(unique),
        "success": ok,
        "failed": len(unique) - ok,
        "max_workers": workers,
        "results": results,
    }
