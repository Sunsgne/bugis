"""Southbound management interface resolution (NETCONF / SSH / SNMP)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.drivers.registry import get_driver
from app.models.device import Device
from app.models.enums import ManagementTransport, Vendor
from app.services import platform_settings as platform_cfg


def effective_transport(device: Device) -> str:
    """Resolve config push / fetch transport for a device."""
    override = getattr(device, "management_transport", None)
    if override and override != ManagementTransport.AUTO:
        return override.value
    return get_driver(device.vendor).transport


def probe_port(device: Device, transport: str | None = None) -> int:
    """TCP/UDP port used for reachability checks."""
    transport = transport or effective_transport(device)
    if transport == "ssh":
        return device.ssh_port or 22
    return device.netconf_port or 830


def netconf_timeout(db: Session | None = None) -> int:
    if db is not None:
        return platform_cfg.get_or_create(db).netconf_timeout
    from app.core.config import settings

    return settings.netconf_timeout


def ssh_timeout(db: Session | None = None) -> int:
    if db is not None:
        row = platform_cfg.get_or_create(db)
        return getattr(row, "ssh_timeout", 30) or 30
    from app.core.config import settings

    return getattr(settings, "ssh_timeout", 30)


def netmiko_device_type(device: Device) -> str:
    if getattr(device, "netmiko_device_type", None):
        return device.netmiko_device_type
    from app.drivers.base import NETMIKO_DEVICE_TYPES

    return NETMIKO_DEVICE_TYPES.get(device.vendor, "autodetect")


def management_defaults(db: Session) -> dict:
    """Platform defaults for device onboarding forms."""
    platform = platform_cfg.get_or_create(db)
    from app.services import snmp_device as snmp_cfg

    snmp = snmp_cfg.snmp_defaults()
    return {
        "netconf_port": getattr(platform, "default_netconf_port", 830) or 830,
        "ssh_port": getattr(platform, "default_ssh_port", 22) or 22,
        "username": getattr(platform, "default_username", None) or "admin",
        "management_transport": ManagementTransport.AUTO.value,
        "netconf_timeout": platform.netconf_timeout,
        "ssh_timeout": getattr(platform, "ssh_timeout", 30) or 30,
        "snmp": snmp,
    }
