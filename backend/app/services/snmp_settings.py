"""Load and persist global SNMP settings."""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device
from app.models.snmp_settings import SnmpSettings
from app.schemas.snmp_settings import SnmpSettingsOut, SnmpSettingsUpdate
from app.services.credential_store import decrypt_value, encrypt_value

DEFAULT_EXCLUDE = ["Null0", "Loopback", "Management", "Console", "InLoopBack", "MEth"]


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
            "community": decrypt_value(row.community) or row.community,
            "write_community": decrypt_value(row.write_community) if row.write_community else None,
            "exclude_name_patterns": row.exclude_name_patterns or list(DEFAULT_EXCLUDE),
            "include_name_patterns": row.include_name_patterns or [],
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
        if key in ("community", "write_community", "v3_auth_password", "v3_priv_password") and value:
            value = encrypt_value(value)
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def effective_community(db: Session, device: Device, override: str | None = None) -> str:
    if override:
        return override
    if device.snmp_community:
        return decrypt_value(device.snmp_community) or device.snmp_community
    cfg = get_or_create(db)
    return decrypt_value(cfg.community) or cfg.community or "public"


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
