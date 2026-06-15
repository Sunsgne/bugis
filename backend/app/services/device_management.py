"""Southbound management interface resolution (NETCONF / SSH / SNMP)."""
from __future__ import annotations

import random
import socket
import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.drivers.registry import get_driver
from app.models.device import Device
from app.models.enums import ManagementTransport, Vendor
from app.services import platform_settings as platform_cfg

SYS_UPTIME_OID = "1.3.6.1.2.1.1.3.0"


def effective_transport(device: Device) -> str:
    """Resolve config push / fetch transport for a device."""
    override = getattr(device, "management_transport", None)
    if override and override != ManagementTransport.AUTO:
        return override.value
    return get_driver(device.vendor).transport


def probe_port(device: Device, transport: str | None = None) -> int:
    """TCP port used for reachability checks."""
    transport = transport or effective_transport(device)
    if transport == "ssh":
        return device.ssh_port or 22
    return device.netconf_port or 830


def _tcp_probe(host: str, port: int, timeout: float = 3.0) -> tuple[bool, float | None, str | None]:
    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            return True, latency_ms, None
    except OSError as exc:
        return False, None, str(exc)


def _snmp_probe(db: Session, device: Device) -> dict[str, Any]:
    from app.services import snmp_device, snmp_settings as snmp_cfg
    from app.services import snmp_hlapi
    from app.services.snmp import _build_credentials

    cfg = snmp_cfg.get_or_create(db)
    eff = snmp_device.effective_snmp(device, cfg)
    if not cfg.enabled or not eff["enabled"]:
        return {"method": "snmp", "ok": False, "skipped": True}

    try:
        import pysnmp  # noqa: F401
    except ImportError:
        return {"method": "snmp", "ok": False, "error": "pysnmp not installed"}

    from pysnmp.hlapi.asyncio import ContextData

    community = snmp_cfg.effective_community(db, device, None)
    creds = _build_credentials(device, cfg, community)
    ctx = (
        ContextData(eff["v3_context_name"])
        if eff["version"] == "3" and eff["v3_context_name"]
        else ContextData()
    )
    started = time.perf_counter()
    raw = snmp_hlapi.get_oid(
        device.mgmt_ip,
        eff["port"] or cfg.port,
        float(cfg.timeout_sec),
        int(cfg.retries),
        creds,
        ctx,
        SYS_UPTIME_OID,
    )
    if raw is None:
        return {"method": "snmp", "ok": False, "error": "SNMP GET sysUpTime failed"}
    return {
        "method": "snmp",
        "ok": True,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def probe_reachability(db: Session, device: Device) -> dict[str, Any]:
    """Try SSH / NETCONF TCP and SNMP UDP; succeed if any path responds."""
    if settings.dry_run:
        reachable = random.random() > 0.1
        return {
            "reachable": reachable,
            "latency_ms": round(random.uniform(0.5, 12.0), 2) if reachable else None,
            "method": "dry_run" if reachable else None,
            "probes": [],
        }

    probes: list[dict[str, Any]] = []
    ports: list[tuple[str, int]] = []
    for label, port in (
        ("tcp_ssh", device.ssh_port or 22),
        ("tcp_netconf", device.netconf_port or 830),
    ):
        if port and not any(existing == port for _, existing in ports):
            ports.append((label, port))

    for label, port in ports:
        ok, latency_ms, error = _tcp_probe(device.mgmt_ip, port)
        probe = {"method": label, "port": port, "ok": ok}
        if error:
            probe["error"] = error
        probes.append(probe)
        if ok:
            return {
                "reachable": True,
                "latency_ms": latency_ms,
                "method": label,
                "probes": probes,
            }

    snmp_probe = _snmp_probe(db, device)
    if not snmp_probe.get("skipped"):
        probes.append(snmp_probe)
    if snmp_probe.get("ok"):
        return {
            "reachable": True,
            "latency_ms": snmp_probe.get("latency_ms"),
            "method": "snmp",
            "probes": probes,
        }

    return {
        "reachable": False,
        "latency_ms": None,
        "method": None,
        "probes": probes,
    }


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
