"""Configuration management: assemble device running-config & version snapshots.

Ties provisioning together with a device-centric view: a device's running
configuration is the assembly of every active circuit's rendered config that
landed on that device. Snapshots are versioned so operators can back up, view
history and diff configurations.
"""
from __future__ import annotations

import difflib
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit, CircuitEndpoint
from app.models.config_job import ConfigJob
from app.models.config_snapshot import DeviceConfigSnapshot
from app.models.device import Device
from app.models.enums import CircuitStatus
from app.models.workorder import WorkOrder


def build_running_config(db: Session, device: Device) -> str:
    """Assemble the device's running config from its latest pushed jobs."""
    header = [
        f"! ===== running-config: {device.name} ({device.vendor.value}) =====",
        f"! mgmt={device.mgmt_ip} loopback={device.loopback_ip or '-'} "
        f"asn={device.bgp_asn or '-'} role={device.role.value}",
        f"! generated={datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "!",
    ]
    # Active circuits that attach on this device.
    circuit_ids = db.execute(
        select(CircuitEndpoint.circuit_id)
        .join(Circuit, Circuit.id == CircuitEndpoint.circuit_id)
        .where(
            CircuitEndpoint.device_id == device.id,
            Circuit.status == CircuitStatus.ACTIVE,
        )
        .distinct()
    ).scalars().all()

    blocks: list[str] = []
    for cid in circuit_ids:
        circuit = db.get(Circuit, cid)
        job = db.execute(
            select(ConfigJob)
            .join(WorkOrder, WorkOrder.id == ConfigJob.work_order_id)
            .where(
                WorkOrder.circuit_id == cid,
                ConfigJob.device_id == device.id,
                ConfigJob.operation == "apply",
            )
            .order_by(ConfigJob.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if job and job.rendered_config:
            blocks.append(
                f"! ---- circuit {circuit.code} ({circuit.service_type.value}) ----\n"
                + job.rendered_config.strip()
            )
    if not blocks:
        blocks.append("! (no active service configuration on this device)")
    return "\n".join(header) + "\n" + "\n!\n".join(blocks) + "\n"


def snapshot_device(
    db: Session, device: Device, source: str = "backup",
    note: str | None = None, created_by: str | None = None,
) -> DeviceConfigSnapshot:
    content = build_running_config(db, device)
    version = (db.scalar(
        select(func.coalesce(func.max(DeviceConfigSnapshot.version), 0)).where(
            DeviceConfigSnapshot.device_id == device.id
        )
    ) or 0) + 1
    snap = DeviceConfigSnapshot(
        device_id=device.id, version=version, source=source,
        content=content, note=note, created_by=created_by,
    )
    db.add(snap)
    db.flush()
    return snap


def diff_snapshots(a: DeviceConfigSnapshot | None, b: DeviceConfigSnapshot) -> str:
    left = (a.content if a else "").splitlines()
    right = b.content.splitlines()
    return "\n".join(
        difflib.unified_diff(
            left, right,
            fromfile=f"v{a.version}" if a else "empty",
            tofile=f"v{b.version}", lineterm="",
        )
    )
