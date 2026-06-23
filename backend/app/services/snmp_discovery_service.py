"""SNMP IF-MIB interface discovery — post-provision and scheduled sweeps."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.circuit import Circuit
from app.models.device import Device
from app.models.enums import DeviceStatus
from app.services import port_inventory, snmp, snmp_device, snmp_settings as snmp_cfg

logger = logging.getLogger(__name__)

_bg_pool: ThreadPoolExecutor | None = None


def _background_pool() -> ThreadPoolExecutor:
    global _bg_pool
    if _bg_pool is None:
        workers = max(1, int(getattr(settings, "provision_max_concurrency", 4) or 4))
        _bg_pool = ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="snmp-discover-bg"
        )
    return _bg_pool


def discover_device(db: Session, device: Device) -> dict:
    """Run IF-MIB discovery + S-VID rescan for one device (best-effort)."""
    cfg = snmp_cfg.get_or_create(db)
    effective = snmp_device.effective_snmp(device)
    if not cfg.enabled or not effective["enabled"]:
        return {
            "device_id": device.id,
            "device": device.name,
            "success": True,
            "skipped": True,
            "reason": "snmp_disabled",
        }
    try:
        ifaces = snmp.discover_interfaces(db, device)
        scan = port_inventory.scan_device(db, device, include_legacy=False)
        return {
            "device_id": device.id,
            "device": device.name,
            "success": True,
            "interfaces": len(ifaces),
            "svid_scan": scan,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("SNMP discover failed for %s: %s", device.name, exc)
        return {
            "device_id": device.id,
            "device": device.name,
            "success": False,
            "error": str(exc),
        }


def discover_devices(
    db: Session,
    device_ids: list[int],
    *,
    max_workers: int | None = None,
) -> dict:
    """Discover interfaces on multiple devices (sequential when one id)."""
    unique = list(dict.fromkeys(device_ids))
    if not unique:
        return {"devices": 0, "success": 0, "failed": 0, "skipped": 0, "results": []}

    if len(unique) == 1:
        device = db.get(Device, unique[0])
        if not device:
            return {
                "devices": 1,
                "success": 0,
                "failed": 1,
                "skipped": 0,
                "results": [{"device_id": unique[0], "success": False, "error": "not found"}],
            }
        result = discover_device(db, device)
        ok = bool(result.get("success") and not result.get("skipped"))
        skipped = bool(result.get("skipped"))
        return {
            "devices": 1,
            "success": 1 if ok else 0,
            "failed": 0 if (ok or skipped) else 1,
            "skipped": 1 if skipped else 0,
            "results": [result],
        }

    order = {did: idx for idx, did in enumerate(unique)}
    workers = min(max(1, max_workers or settings.provision_max_concurrency), len(unique))

    def _one(device_id: int) -> dict:
        db = SessionLocal()
        try:
            device = db.get(Device, device_id)
            if not device:
                return {"device_id": device_id, "success": False, "error": "not found"}
            result = discover_device(db, device)
            db.commit()
            return result
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("SNMP discover worker failed for id=%s", device_id)
            return {"device_id": device_id, "success": False, "error": str(exc)}
        finally:
            db.close()

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, did) for did in unique]
        for fut in as_completed(futures):
            results.append(fut.result())
    results.sort(key=lambda r: order.get(r.get("device_id"), 999))

    success = sum(
        1 for r in results if r.get("success") and not r.get("skipped")
    )
    skipped = sum(1 for r in results if r.get("skipped"))
    failed = len(results) - success - skipped
    return {
        "devices": len(unique),
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "results": results,
    }


def circuit_endpoint_device_ids(circuit: Circuit) -> list[int]:
    seen: set[int] = set()
    ids: list[int] = []
    for ep in circuit.endpoints:
        if ep.device_id and ep.device_id not in seen:
            seen.add(ep.device_id)
            ids.append(ep.device_id)
    return ids


def discover_circuit_endpoints(db: Session, circuit: Circuit) -> dict:
    """SNMP-discover every endpoint device on a circuit."""
    device_ids = circuit_endpoint_device_ids(circuit)
    summary = discover_devices(db, device_ids)
    summary["circuit_id"] = circuit.id
    summary["circuit_code"] = circuit.code
    return summary


def schedule_circuit_endpoint_discovery(circuit_id: int) -> None:
    """Fire-and-forget SNMP discovery for all endpoint devices on a circuit."""

    def _run() -> None:
        db = SessionLocal()
        try:
            circuit = db.get(Circuit, circuit_id)
            if not circuit:
                return
            discover_circuit_endpoints(db, circuit)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("background SNMP discover failed for circuit_id=%s", circuit_id)
        finally:
            db.close()

    _background_pool().submit(_run)


def snmp_discover_interval_seconds(db: Session) -> int:
    from app.services import platform_settings as platform_cfg

    plat = platform_cfg.get_or_create(db)
    return max(
        300,
        int(getattr(plat, "snmp_discover_interval_seconds", None) or settings.snmp_discover_interval_seconds),
    )


def snmp_discover_enabled(db: Session) -> bool:
    from app.services import platform_settings as platform_cfg

    plat = platform_cfg.get_or_create(db)
    if hasattr(plat, "snmp_discover_enabled"):
        return bool(plat.snmp_discover_enabled)
    return bool(settings.snmp_discover_enabled)


def interval_elapsed(db: Session, interval: int) -> bool:
    from app.services import platform_settings as platform_cfg

    plat = platform_cfg.get_or_create(db)
    last = getattr(plat, "last_snmp_discover_at", None)
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - last).total_seconds()
    return elapsed >= interval


def is_scheduled_discover_due(db: Session) -> bool:
    if not snmp_discover_enabled(db):
        return False
    cfg = snmp_cfg.get_or_create(db)
    if not cfg.enabled:
        return False
    return interval_elapsed(db, snmp_discover_interval_seconds(db))


def scheduled_discover_all_online(db: Session, *, created_by: str = "scheduler") -> dict:
    """SNMP-discover every online device (scheduled sweep)."""
    from app.services import platform_settings as platform_cfg

    if not is_scheduled_discover_due(db):
        return {"skipped": True, "reason": "not_due_or_disabled"}

    devices = db.execute(
        select(Device).where(Device.status == DeviceStatus.ONLINE)
    ).scalars().all()
    device_ids = [d.id for d in devices]
    if not device_ids:
        plat = platform_cfg.get_or_create(db)
        plat.last_snmp_discover_at = datetime.now(timezone.utc)
        return {
            "skipped": False,
            "devices": 0,
            "success": 0,
            "failed": 0,
            "skipped_devices": 0,
            "created_by": created_by,
            "results": [],
        }

    plat = platform_cfg.get_or_create(db)
    max_workers = max(1, int(getattr(plat, "provision_max_concurrency", 4) or 4))
    batch = discover_devices(db, device_ids, max_workers=max_workers)
    plat.last_snmp_discover_at = datetime.now(timezone.utc)
    return {
        "skipped": False,
        "created_by": created_by,
        "devices": batch.get("devices", 0),
        "success": batch.get("success", 0),
        "failed": batch.get("failed", 0),
        "skipped_devices": batch.get("skipped", 0),
        "results": batch.get("results") or [],
    }
