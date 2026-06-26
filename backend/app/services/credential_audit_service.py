"""Audit southbound credentials — detect missing or undecryptable secrets."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.snmp_settings import SnmpSettings
from app.services.credential_store import (
    _SENSITIVE_DEVICE_FIELDS,
    decrypt_value,
    is_encrypted,
)
from app.services import snmp_settings as snmp_cfg

_FIELD_LABELS = {
    "password": "SSH 密码",
    "enable_password": "Enable 密码",
    "snmp_community": "SNMP Community",
    "snmp_v3_auth_password": "SNMPv3 认证密码",
    "snmp_v3_priv_password": "SNMPv3 加密密码",
}


def _check_field(raw: str | None, *, required: bool = False) -> str | None:
    if not raw:
        return "missing" if required else None
    if is_encrypted(raw) and decrypt_value(raw) is None:
        return "decrypt_failed"
    return None


def audit_device(device: Device) -> dict:
    """Return credential issues for one device (empty issues = OK)."""
    issues: list[dict] = []
    ssh_required = bool(device.username)
    snmp_required = bool(getattr(device, "snmp_enabled", False))

    for field in _SENSITIVE_DEVICE_FIELDS:
        raw = getattr(device, field, None)
        required = field == "password" and ssh_required
        if field == "snmp_community" and snmp_required and not raw:
            required = True
        problem = _check_field(raw, required=required)
        if problem:
            issues.append({
                "field": field,
                "label": _FIELD_LABELS.get(field, field),
                "problem": problem,
            })

    return {
        "device_id": device.id,
        "device": device.name,
        "mgmt_ip": device.mgmt_ip,
        "username": device.username,
        "ok": not issues,
        "issues": issues,
    }


def audit_snmp_settings(db: Session) -> dict | None:
    row = snmp_cfg.get_or_create(db)
    issues: list[dict] = []
    if not row.enabled:
        return None
    for field, label in (
        ("community", "平台 SNMP Community"),
        ("write_community", "平台 SNMP 写 Community"),
        ("v3_auth_password", "平台 SNMPv3 认证密码"),
        ("v3_priv_password", "平台 SNMPv3 加密密码"),
    ):
        raw = getattr(row, field, None)
        problem = _check_field(raw, required=field == "community")
        if problem:
            issues.append({"field": field, "label": label, "problem": problem})
    if not issues:
        return None
    return {"scope": "platform_snmp", "ok": False, "issues": issues}


def audit_all_devices(db: Session) -> dict:
    devices = db.execute(select(Device).order_by(Device.id)).scalars().all()
    rows = [audit_device(d) for d in devices]
    bad = [r for r in rows if not r["ok"]]
    platform = audit_snmp_settings(db)
    return {
        "total": len(rows),
        "healthy": len(rows) - len(bad),
        "unhealthy": len(bad),
        "platform_snmp": platform,
        "devices": bad,
    }
