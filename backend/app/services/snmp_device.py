"""Per-device SNMP effective settings (global defaults + optional overrides)."""
from __future__ import annotations

from app.core.config import settings
from app.models.device import Device

DEFAULT_SNMP_PORT = 161
DEFAULT_SNMP_VERSION = "2c"


def snmp_defaults() -> dict:
    return {
        "enabled": True,
        "port": DEFAULT_SNMP_PORT,
        "community": settings.baseline_snmp_community,
        "version": DEFAULT_SNMP_VERSION,
    }


def effective_snmp(device: Device) -> dict:
    """Resolved SNMP parameters for southbound walks."""
    defaults = snmp_defaults()
    enabled = getattr(device, "snmp_enabled", None)
    if enabled is None:
        enabled = defaults["enabled"]
    port = getattr(device, "snmp_port", None) or defaults["port"]
    community = (
        getattr(device, "snmp_community", None)
        or getattr(device, "password", None)
        or defaults["community"]
    )
    version = getattr(device, "snmp_version", None) or defaults["version"]
    return {
        "enabled": enabled,
        "port": port,
        "community": community,
        "version": version,
    }
