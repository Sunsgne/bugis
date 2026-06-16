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


def latest_baseline(db: Session, device_id: int) -> DeviceConfigSnapshot | None:
    return db.execute(
        select(DeviceConfigSnapshot)
        .where(
            DeviceConfigSnapshot.device_id == device_id,
            DeviceConfigSnapshot.source == "init",
        )
        .order_by(DeviceConfigSnapshot.version.desc())
        .limit(1)
    ).scalar_one_or_none()


def latest_learned(db: Session, device_id: int) -> DeviceConfigSnapshot | None:
    """Most recent snapshot from live-network auto-learn."""
    return db.execute(
        select(DeviceConfigSnapshot)
        .where(
            DeviceConfigSnapshot.device_id == device_id,
            DeviceConfigSnapshot.source == "learn",
        )
        .order_by(DeviceConfigSnapshot.version.desc())
        .limit(1)
    ).scalar_one_or_none()


def add_snapshot(
    db: Session, device: Device, content: str, source: str = "backup",
    note: str | None = None, created_by: str | None = None,
) -> DeviceConfigSnapshot:
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


def build_running_config(db: Session, device: Device) -> str:
    """Assemble the device's running config: baseline (init) + service blocks."""
    header = [
        f"! ===== running-config: {device.name} ({device.vendor.value}) =====",
        f"! mgmt={device.mgmt_ip} loopback={device.loopback_ip or '-'} "
        f"asn={device.bgp_asn or '-'} role={device.role.value}",
        f"! generated={datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "!",
    ]
    baseline = latest_baseline(db, device.id)
    baseline_block = (
        "! ---- baseline (init) ----\n" + baseline.content.strip() + "\n!\n"
        if baseline else ""
    )
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
    return "\n".join(header) + "\n" + baseline_block + "\n!\n".join(blocks) + "\n"


def snapshot_device(
    db: Session, device: Device, source: str = "backup",
    note: str | None = None, created_by: str | None = None,
) -> DeviceConfigSnapshot:
    """Persist platform-assembled desired config as a snapshot (legacy helper)."""
    content = build_running_config(db, device)
    return add_snapshot(
        db, device, content, source=source, note=note, created_by=created_by
    )


def backup_device_running_config(
    db: Session,
    device: Device,
    *,
    note: str | None = None,
    created_by: str | None = None,
) -> tuple[DeviceConfigSnapshot, dict]:
    """Pull live running-config from the device and version it as backup."""
    from app.services import config_fetch, device_management

    probe = device_management.probe_reachability(db, device)
    if not probe["reachable"]:
        errors = [
            f"{p.get('method')}:{p.get('error')}"
            for p in probe.get("probes") or []
            if p.get("error")
        ]
        detail = "; ".join(errors) if errors else "unreachable"
        raise ValueError(f"设备不可达，无法备份现网配置 ({detail})")

    ok, content, fetch_err = config_fetch.fetch_running_config(device)
    fetched_live = ok and bool(content.strip())
    from_learned_version: int | None = None

    if not fetched_live:
        learned = latest_learned(db, device.id)
        if learned and (learned.content or "").strip():
            content = learned.content
            from_learned_version = learned.version
            suffix = f"设备拉取失败，复用现网学习 v{learned.version}"
            note = f"{note} · {suffix}" if note else suffix
        else:
            raise ValueError(fetch_err or "无法获取设备 running-config")

    snap = add_snapshot(
        db,
        device,
        content,
        source="backup",
        note=note or "现网 running-config 备份",
        created_by=created_by,
    )
    return snap, {
        "lines": len(content.splitlines()),
        "fetched_live": fetched_live,
        "from_learned_version": from_learned_version,
    }


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


def diff_platform_vs_learned(db: Session, device: Device) -> str:
    """Diff platform-assembled running config vs latest learned live config."""
    learned = latest_learned(db, device.id)
    if not learned:
        return ""
    platform = build_running_config(db, device)
    left = platform.splitlines()
    right = learned.content.splitlines()
    return "\n".join(
        difflib.unified_diff(
            left, right,
            fromfile="platform-assembled",
            tofile=f"learned-v{learned.version}",
            lineterm="",
        )
    )
