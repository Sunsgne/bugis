"""Device reachability probe + S-VID inventory scan."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device
from app.models.enums import DeviceStatus
from app.services import device_management, port_inventory, snmp
from app.services import snmp_settings as snmp_cfg


def run_device_check(db: Session, device_id: int) -> dict:
    """Probe reachability, refresh S-VID inventory, optional SNMP discover."""
    device = db.get(Device, device_id)
    if not device:
        return {
            "device_id": device_id,
            "success": False,
            "error": "not found",
        }

    probe = device_management.probe_reachability(db, device)
    reachable = probe["reachable"]
    latency = probe.get("latency_ms")
    transport = device_management.effective_transport(device)
    device.status = DeviceStatus.ONLINE if reachable else DeviceStatus.OFFLINE
    svid_scan: dict | None = None
    if reachable:
        svid_scan = port_inventory.scan_device(
            db, device, include_legacy=settings.dry_run
        )
        cfg = snmp_cfg.get_or_create(db)
        if cfg.auto_discover_on_check:
            snmp.discover_interfaces(db, device)

    return {
        "device_id": device.id,
        "success": True,
        "device": device.name,
        "mgmt_ip": device.mgmt_ip,
        "mgmt_ip_backup": device.mgmt_ip_backup,
        "mgmt_ip_primary_label": device.mgmt_ip_primary_label or "管理网",
        "mgmt_ip_backup_label": device.mgmt_ip_backup_label or "公网",
        "mgmt_ip_active": device.mgmt_ip_active,
        "mgmt_ip_active_role": device.mgmt_ip_active_role,
        "mgmt_ip_active_label": (
            (device.mgmt_ip_primary_label or "管理网")
            if device.mgmt_ip_active_role == "primary"
            else (device.mgmt_ip_backup_label or "公网")
            if device.mgmt_ip_active_role == "backup"
            else None
        ),
        "transport": transport,
        "reachable": reachable,
        "latency_ms": latency,
        "method": probe.get("method"),
        "probes": probe.get("probes") or [],
        "status": device.status.value,
        "dry_run": settings.dry_run,
        "last_reachability_at": (
            device.last_reachability_at.isoformat() if device.last_reachability_at else None
        ),
        "svid_scan": svid_scan,
    }
