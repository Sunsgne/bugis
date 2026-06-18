"""Interface administration helpers — bulk interface-description edits.

Lets operators rename/annotate physical (and logical) interface descriptions and
push them to the device with the correct per-vendor syntax. Pushes go through the
vendor driver (NETCONF/CLI) and honor dry-run, so nothing reaches a live box in
simulation mode.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.drivers import get_driver
from app.models.device import Device, DeviceInterface
from app.models.enums import Vendor


def _desc_lines(vendor: Vendor, name: str, description: str | None) -> list[str]:
    """Render the vendor CLI to set (or clear) one interface description."""
    desc = (description or "").strip()
    if vendor == Vendor.JUNIPER:
        if desc:
            return [f'set interfaces {name} description "{desc}"']
        return [f"delete interfaces {name} description"]
    # Comware (H3C), VRP (Huawei), IOS-XR (Cisco), EOS (Arista), FRR/vtysh.
    negate = "undo" if vendor in (Vendor.H3C, Vendor.HUAWEI) else "no"
    lines = [f"interface {name}"]
    if desc:
        lines.append(f" description {desc}")
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
