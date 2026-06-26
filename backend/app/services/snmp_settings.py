"""Load and persist global SNMP settings."""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device
from app.models.snmp_settings import SnmpSettings
from app.schemas.snmp_settings import SnmpSettingsOut, SnmpSettingsUpdate
from app.services.credential_store import decrypt_value, encrypt_value, is_encrypted

DEFAULT_EXCLUDE = ["Null0", "Loopback", "Management", "Console", "InLoopBack", "MEth"]


def _resolved_secret(raw: str | None, *, default: str | None = None) -> str | None:
    """Return decrypted plaintext; never fall back to enc$ ciphertext."""
    if not raw:
        return default
    dec = decrypt_value(raw)
    if dec is not None:
        return dec
    if is_encrypted(raw):
        return default
    return raw


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
            "community": _resolved_secret(row.community) or "",
            "write_community": _resolved_secret(row.write_community),
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
        return _resolved_secret(device.snmp_community) or "public"
    cfg = get_or_create(db)
    return _resolved_secret(cfg.community, default="public") or "public"


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
