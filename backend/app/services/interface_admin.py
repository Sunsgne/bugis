"""Interface administration helpers — bulk interface-description edits.

Lets operators rename/annotate physical (and logical) interface descriptions and
push them to the device with the correct per-vendor syntax. Pushes go through the
vendor driver (NETCONF/CLI) and honor dry-run, so nothing reaches a live box in
simulation mode.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.drivers import get_driver
from app.models.device import Device, DeviceInterface
from app.models.enums import Vendor


def _quote_description(vendor: Vendor, desc: str) -> str:
    """Wrap description for vendor CLI when required by that NOS."""
    if not desc:
        return desc
    if vendor == Vendor.JUNIPER:
        return desc.replace('"', '\\"')
    # VRP (Huawei) / Comware (H3C): colons/parens are normal in port labels — no quotes.
    if vendor in (Vendor.H3C, Vendor.HUAWEI):
        return desc
    if re.search(r'[\s#;"\'\\]', desc):
        escaped = desc.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return desc


def _cli_iface_name(name: str, vendor: Vendor) -> str:
    """Normalize interface name for device CLI (Vlan-interface2600, etc.)."""
    from app.services.port_inventory import _normalize_iface, is_vlan_interface_name

    norm = _normalize_iface(name)
    if vendor == Vendor.H3C and is_vlan_interface_name(norm):
        m = re.match(r"^(?:Vlan-interface|Vlan)(\d+)$", norm, re.IGNORECASE)
        if m:
            return f"Vlan-interface{m.group(1)}"
    if vendor == Vendor.HUAWEI and is_vlan_interface_name(norm):
        m = re.match(r"^(?:Vlanif|Vlan-interface|Vlan)(\d+)$", norm, re.IGNORECASE)
        if m:
            return f"Vlanif{m.group(1)}"
    return norm


def _desc_lines(vendor: Vendor, name: str, description: str | None) -> list[str]:
    """Render the vendor CLI to set (or clear) one interface description."""
    desc = (description or "").strip()
    cli_name = _cli_iface_name(name, vendor)
    if vendor == Vendor.JUNIPER:
        if desc:
            return [f'set interfaces {cli_name} description "{_quote_description(vendor, desc)}"']
        return [f"delete interfaces {cli_name} description"]
    # Comware (H3C), VRP (Huawei), IOS-XR (Cisco), EOS (Arista), FRR/vtysh.
    negate = "undo" if vendor in (Vendor.H3C, Vendor.HUAWEI) else "no"
    lines = [f"interface {cli_name}"]
    if desc:
        lines.append(f" description {_quote_description(vendor, desc)}")
    else:
        lines.append(f" {negate} description")
    return lines


def render_descriptions(vendor: Vendor, items: list[tuple[str, str | None]]) -> str:
    """Render a full CLI block setting many interface descriptions."""
    blocks: list[str] = []
    for name, desc in items:
        blocks.extend(_desc_lines(vendor, name, desc))
        if vendor != Vendor.JUNIPER:
            blocks.append("#")
    return "\n".join(blocks).strip() + "\n"


def apply_descriptions(
    db: Session,
    device: Device,
    items: list[tuple[str, str | None]],
    *,
    push: bool = True,
) -> dict:
    """Persist interface descriptions and optionally push them to the device.

    Unknown interface names are created as rows (discovered_via='manual') so a
    description can be set before SNMP/learn has populated the interface.
    """
    existing = {
        i.name: i
        for i in db.execute(
            select(DeviceInterface).where(DeviceInterface.device_id == device.id)
        ).scalars().all()
    }
    results: list[dict] = []
    applied: list[tuple[str, str | None]] = []
    for name, desc in items:
        name = (name or "").strip()
        if not name:
            results.append({"name": name, "description": desc, "updated": False,
                            "note": "接口名为空，已跳过"})
            continue
        desc_norm = (desc or "").strip() or None
        row = existing.get(name)
        if row is None:
            row = DeviceInterface(device_id=device.id, name=name, discovered_via="manual")
            db.add(row)
            existing[name] = row
        row.description = desc_norm
        applied.append((name, desc_norm))
        results.append({"name": name, "description": desc_norm, "updated": True})

    rendered = render_descriptions(device.vendor, applied) if applied else ""
    output: str | None = None
    pushed = False
    dry_run = settings.dry_run
    if push and applied:
        driver = get_driver(device.vendor)
        result = driver.push(device, rendered, dry_run=settings.dry_run)
        output = result.output
        pushed = result.success
        dry_run = result.dry_run
        if not result.success:
            for r in results:
                if r["updated"]:
                    r["note"] = "已保存，但下发失败"
    db.commit()
    return {
        "device": device.name,
        "updated": len(applied),
        "pushed": pushed,
        "dry_run": dry_run,
        "output": output,
        "rendered": rendered or None,
        "results": results,
    }


def apply_descriptions_parallel(
    jobs: list[tuple[int, list[tuple[str, str | None]]]],
    *,
    push: bool = True,
    max_workers: int = 4,
) -> list[dict]:
    """Push interface descriptions to multiple devices concurrently."""
    from app.core.database import SessionLocal
    from app.services import device_management
    from concurrent.futures import ThreadPoolExecutor, as_completed

    seen: set[int] = set()
    unique_jobs: list[tuple[int, list[tuple[str, str | None]]]] = []
    for device_id, items in jobs:
        if device_id in seen:
            continue
        seen.add(device_id)
        unique_jobs.append((device_id, items))
    if not unique_jobs:
        return []

    def _one(device_id: int, items: list[tuple[str, str | None]]) -> dict:
        db = SessionLocal()
        try:
            device = db.get(Device, device_id)
            if not device:
                return {
                    "device": str(device_id),
                    "updated": 0,
                    "pushed": False,
                    "dry_run": settings.dry_run,
                    "output": None,
                    "rendered": None,
                    "results": [],
                    "error": "device not found",
                }
            if push and not settings.dry_run:
                try:
                    device_management.ensure_reachable_mgmt_ip(db, device)
                except device_management.MgmtUnreachableError as exc:
                    return {
                        "device": device.name,
                        "updated": 0,
                        "pushed": False,
                        "dry_run": settings.dry_run,
                        "output": None,
                        "rendered": None,
                        "results": [],
                        "error": str(exc),
                    }
            return apply_descriptions(db, device, items, push=push)
        finally:
            db.close()

    if len(unique_jobs) == 1:
        device_id, items = unique_jobs[0]
        return [_one(device_id, items)]

    workers = min(max_workers, len(unique_jobs))
    ordered: list[dict | None] = [None] * len(unique_jobs)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {
            pool.submit(_one, device_id, items): idx
            for idx, (device_id, items) in enumerate(unique_jobs)
        }
        for fut in as_completed(future_map):
            idx = future_map[fut]
            ordered[idx] = fut.result()
    return [r for r in ordered if r is not None]
