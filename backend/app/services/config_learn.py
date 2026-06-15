"""Orchestrate live-network config learning and feed results into platform features."""
from __future__ import annotations

import socket
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device
from app.models.device_learn_run import DeviceLearnRun
from app.models.enums import DeviceStatus
from app.services import config_fetch, config_learn_parse, config_mgmt, port_inventory, snmp
from app.services import snmp_settings as snmp_cfg


def _check_reachable(device: Device) -> tuple[bool, str | None]:
    if settings.dry_run:
        return True, None
    try:
        with socket.create_connection(
            (device.mgmt_ip, device.netconf_port), timeout=3
        ):
            return True, None
    except OSError as exc:
        return False, str(exc)


def _enrich_device(device: Device, inventory: config_learn_parse.LearnedInventory) -> dict:
    """Fill missing device fields from learned inventory."""
    updated: dict[str, object] = {}
    if not device.loopback_ip and inventory.loopback_ip:
        device.loopback_ip = inventory.loopback_ip
        updated["loopback_ip"] = inventory.loopback_ip
    if not device.bgp_asn and inventory.bgp_asn:
        device.bgp_asn = inventory.bgp_asn
        updated["bgp_asn"] = inventory.bgp_asn
    if device.status == DeviceStatus.UNKNOWN:
        device.status = DeviceStatus.ONLINE
        updated["status"] = DeviceStatus.ONLINE.value
    return updated


def learn_device(
    db: Session,
    device: Device,
    *,
    created_by: str | None = None,
    discover_snmp: bool = True,
) -> dict:
    """Full learn pipeline: fetch → parse → snapshot → port inventory → enrich."""
    started = datetime.now(timezone.utc)
    reachable, reach_err = _check_reachable(device)
    if not reachable:
        run = DeviceLearnRun(
            device_id=device.id,
            status="failed",
            error=f"device unreachable: {reach_err}",
            created_by=created_by,
        )
        db.add(run)
        db.flush()
        return {
            "device": device.name,
            "success": False,
            "status": "failed",
            "error": run.error,
            "run_id": run.id,
        }

    ok, content, fetch_err = config_fetch.fetch_running_config(device)
    if not ok or not content.strip():
        run = DeviceLearnRun(
            device_id=device.id,
            status="failed",
            error=fetch_err or "empty config",
            created_by=created_by,
        )
        db.add(run)
        db.flush()
        return {
            "device": device.name,
            "success": False,
            "status": "failed",
            "error": run.error,
            "run_id": run.id,
        }

    inventory = config_learn_parse.parse_inventory(content, device.vendor)
    snap = config_mgmt.add_snapshot(
        db,
        device,
        content,
        source="learn",
        note="现网配置自动学习",
        created_by=created_by,
    )

    enriched = _enrich_device(device, inventory)

    svid_scan: dict | None = None
    if discover_snmp:
        cfg = snmp_cfg.get_or_create(db)
        if cfg.auto_discover_on_check:
            snmp.discover_interfaces(db, device)
    svid_scan = port_inventory.scan_device(db, device, include_legacy=False)

    summary = {
        "dry_run": settings.dry_run,
        "reachable": True,
        "config_lines": len(content.splitlines()),
        "inventory": inventory.as_dict(),
        "enriched": enriched,
        "svid_scan": {
            "ports_scanned": svid_scan.get("ports_scanned", 0),
            "total_s_vids": svid_scan.get("total_s_vids", 0),
            "conflicts": len(svid_scan.get("conflicts") or []),
        },
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }

    run = DeviceLearnRun(
        device_id=device.id,
        status="success",
        snapshot_id=snap.id,
        inventory=inventory.as_dict(),
        summary=summary,
        created_by=created_by,
    )
    db.add(run)
    db.flush()

    return {
        "device": device.name,
        "success": True,
        "status": "success",
        "run_id": run.id,
        "snapshot_version": snap.version,
        "snapshot_id": snap.id,
        "inventory": inventory.as_dict(),
        "enriched": enriched,
        "svid_scan": svid_scan,
        "dry_run": settings.dry_run,
    }


def latest_learn_run(db: Session, device_id: int) -> DeviceLearnRun | None:
    return db.execute(
        select(DeviceLearnRun)
        .where(DeviceLearnRun.device_id == device_id)
        .order_by(DeviceLearnRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def learned_state(db: Session, device: Device) -> dict:
    """Current learned inventory summary for API consumers."""
    snap = config_mgmt.latest_learned(db, device.id)
    run = latest_learn_run(db, device.id)
    drift_lines = 0
    if snap:
        drift = config_mgmt.diff_platform_vs_learned(db, device)
        drift_lines = len([ln for ln in drift.splitlines() if ln.startswith("+") or ln.startswith("-")])

    return {
        "device_id": device.id,
        "device": device.name,
        "has_learned_config": snap is not None,
        "latest_snapshot_version": snap.version if snap else None,
        "latest_snapshot_at": snap.created_at.isoformat() if snap and snap.created_at else None,
        "last_run_status": run.status if run else None,
        "last_run_at": run.created_at.isoformat() if run and run.created_at else None,
        "inventory": run.inventory if run else None,
        "drift_line_count": drift_lines,
    }


def learn_devices_batch(
    db: Session,
    device_ids: list[int],
    *,
    created_by: str | None = None,
) -> dict:
    """Learn config for multiple devices (e.g. after CSV import)."""
    results: list[dict] = []
    for did in device_ids:
        device = db.get(Device, did)
        if not device:
            results.append({"device_id": did, "success": False, "error": "not found"})
            continue
        results.append(learn_device(db, device, created_by=created_by))
    ok = sum(1 for r in results if r.get("success"))
    return {"total": len(results), "success": ok, "failed": len(results) - ok, "results": results}
