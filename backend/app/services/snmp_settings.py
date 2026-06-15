"""Load and persist global SNMP settings."""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device
from app.models.snmp_settings import SnmpSettings
from app.schemas.snmp_settings import SnmpSettingsOut, SnmpSettingsUpdate

DEFAULT_EXCLUDE = ["Null0", "Loopback", "Vlan-interface", "Management", "Console"]


def get_or_create(db: Session) -> SnmpSettings:
    row = db.get(SnmpSettings, 1)
    if row:
        return row
    row = SnmpSettings(
        id=1,
        community=settings.baseline_snmp_community,
        baseline_community=settings.baseline_snmp_community,
        exclude_name_patterns=list(DEFAULT_EXCLUDE),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def to_out(row: SnmpSettings) -> SnmpSettingsOut:
    data = SnmpSettingsOut.model_validate(row, from_attributes=True)
    return data.model_copy(
        update={
            "v3_auth_password_set": bool(row.v3_auth_password),
            "v3_priv_password_set": bool(row.v3_priv_password),
            "v3_auth_password": None,
            "v3_priv_password": None,
        }
    )


def update_settings(db: Session, payload: SnmpSettingsUpdate) -> SnmpSettings:
    row = get_or_create(db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key in ("v3_auth_password", "v3_priv_password") and value == "":
            continue
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def effective_community(db: Session, device: Device, override: str | None = None) -> str:
    if override:
        return override
    if device.snmp_community:
        return device.snmp_community
    cfg = get_or_create(db)
    if cfg.prefer_device_community and device.password:
        return device.password
    return cfg.community or "public"


def interface_allowed(name: str, cfg: SnmpSettings) -> bool:
    include = cfg.include_name_patterns or []
    exclude = cfg.exclude_name_patterns or []
    if include:
        if not any(re.search(p, name, re.I) for p in include):
            return False
    for pat in exclude:
        if re.search(pat, name, re.I):
            return False
    return True
