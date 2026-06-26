"""Per-device SNMP effective settings (global defaults + optional overrides)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.credential_store import decrypt_value
from app.models.device import Device
from app.models.snmp_settings import SnmpSettings

DEFAULT_SNMP_PORT = 161
DEFAULT_SNMP_VERSION = "2c"


def snmp_defaults(db: Session | None = None) -> dict:
    port = DEFAULT_SNMP_PORT
    community = settings.baseline_snmp_community
    version = DEFAULT_SNMP_VERSION
    enabled = True
    if db is not None:
        from app.services import snmp_settings as snmp_cfg

        cfg = snmp_cfg.get_or_create(db)
        enabled = cfg.enabled
        port = cfg.port
        community = snmp_cfg._resolved_secret(cfg.community, default=settings.baseline_snmp_community) or settings.baseline_snmp_community
        version = cfg.version
    return {
        "enabled": enabled,
        "port": port,
        "community": community,
        "version": version,
    }


def effective_snmp(device: Device, cfg: SnmpSettings | None = None) -> dict:
    """Resolved SNMP parameters for southbound walks."""
    defaults = snmp_defaults()
    enabled = getattr(device, "snmp_enabled", None)
    if enabled is None:
        enabled = defaults["enabled"]
    port = getattr(device, "snmp_port", None) or defaults["port"]
    community = decrypt_value(getattr(device, "snmp_community", None)) or defaults["community"]
    version = getattr(device, "snmp_version", None) or defaults["version"]
    if cfg is not None and version == "3":
        v3_username = device.snmp_v3_username or cfg.v3_username
        v3_security_level = device.snmp_v3_security_level or cfg.v3_security_level
        v3_auth_protocol = device.snmp_v3_auth_protocol or cfg.v3_auth_protocol
        v3_priv_protocol = device.snmp_v3_priv_protocol or cfg.v3_priv_protocol
        v3_auth_password = decrypt_value(device.snmp_v3_auth_password or cfg.v3_auth_password)
        v3_priv_password = decrypt_value(device.snmp_v3_priv_password or cfg.v3_priv_password)
        v3_context = cfg.v3_context_name
    else:
        v3_username = device.snmp_v3_username
        v3_security_level = device.snmp_v3_security_level
        v3_auth_protocol = device.snmp_v3_auth_protocol
        v3_priv_protocol = device.snmp_v3_priv_protocol
        v3_auth_password = decrypt_value(device.snmp_v3_auth_password)
        v3_priv_password = decrypt_value(device.snmp_v3_priv_password)
        v3_context = None
    return {
        "enabled": enabled,
        "port": port,
        "community": community,
        "version": version,
        "v3_username": v3_username,
        "v3_security_level": v3_security_level,
        "v3_auth_protocol": v3_auth_protocol,
        "v3_priv_protocol": v3_priv_protocol,
        "v3_auth_password": v3_auth_password,
        "v3_priv_password": v3_priv_password,
        "v3_context_name": v3_context,
    }
