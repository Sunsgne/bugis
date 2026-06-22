"""SNMP IF-MIB interface discovery for a single device."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device, DeviceInterface
from app.models.enums import Vendor
from app.services import device_management, port_inventory, snmp, snmp_device


def run_snmp_discover(db: Session, device_id: int) -> dict:
    """Discover interfaces via SNMP (or config fallback) and refresh S-VID scan."""
    device = db.get(Device, device_id)
    if not device:
        return {
            "device_id": device_id,
            "success": False,
            "error": "device not found",
        }

    cfg = snmp_device.effective_snmp(device)
    if not cfg["enabled"]:
        return {
            "device_id": device.id,
            "device": device.name,
            "success": False,
            "error": "该设备未启用 SNMP，请在设备设置中开启",
        }

    try:
        snmp.discover_interfaces(db, device)
    except device_management.MgmtUnreachableError as exc:
        return {
            "device_id": device.id,
            "device": device.name,
            "success": False,
            "error": str(exc),
        }
    except (RuntimeError, ImportError, ModuleNotFoundError) as exc:
        return {
            "device_id": device.id,
            "device": device.name,
            "success": False,
            "error": str(exc),
        }

    port_inventory.scan_device(db, device)

    all_ifaces = db.execute(
        select(DeviceInterface).where(DeviceInterface.device_id == device.id)
    ).scalars().all()
    if device.vendor == Vendor.HUAWEI:
        all_ifaces = [
            row for row in all_ifaces if not port_inventory.is_huawei_subinterface(row.name)
        ]

    sim_count = sum(1 for row in all_ifaces if row.discovered_via == "snmp-sim")
    cfg_count = sum(1 for row in all_ifaces if row.discovered_via == "running-config")
    snmp_count = sum(1 for row in all_ifaces if row.discovered_via == "snmp")
    svid_count = sum(1 for row in all_ifaces if row.used_s_vids)

    return {
        "device_id": device.id,
        "device": device.name,
        "success": True,
        "interface_count": len(all_ifaces),
        "snmp_count": snmp_count,
        "sim_count": sim_count,
        "config_count": cfg_count,
        "svid_port_count": svid_count,
    }
