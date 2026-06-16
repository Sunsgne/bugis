"""Dual management IP resolution and reachability probing."""
from __future__ import annotations

import socket
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.drivers.registry import get_driver
from app.models.device import Device
from app.models.enums import ManagementTransport, Vendor
from app.services import platform_settings as platform_cfg

SYS_UPTIME_OID = "1.3.6.1.2.1.1.3.0"


class MgmtUnreachableError(RuntimeError):
    """Raised when no primary/backup management IP is reachable."""

    def __init__(self, message: str, *, probe: dict[str, Any] | None = None):
        super().__init__(message)
        self.probe = probe or {}


def effective_transport(device: Device) -> str:
    """Resolve config push / fetch transport for a device."""
    override = getattr(device, "management_transport", None)
    if override and override != ManagementTransport.AUTO:
        return override.value
    return get_driver(device.vendor).transport


def mgmt_ip_candidates(device: Device) -> list[dict[str, str]]:
    """Ordered management endpoints: primary then backup."""
    primary_label = device.mgmt_ip_primary_label or "管理网"
    items = [{
        "role": "primary",
        "ip": device.mgmt_ip,
        "label": primary_label,
    }]
    if device.mgmt_ip_backup:
        items.append({
            "role": "backup",
            "ip": device.mgmt_ip_backup,
            "label": device.mgmt_ip_backup_label or "公网",
        })
    return items


def effective_mgmt_ip(device: Device) -> str:
    return device.active_mgmt_ip


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


def _snmp_probe(db: Session | None, device: Device, host: str) -> dict[str, Any]:
    if db is None:
        return {"method": "snmp", "ok": False, "skipped": True, "host": host}
    from app.services import snmp_device, snmp_settings as snmp_cfg
    from app.services import snmp_hlapi
    from app.services.snmp import _build_credentials

    cfg = snmp_cfg.get_or_create(db)
    eff = snmp_device.effective_snmp(device, cfg)
    if not cfg.enabled or not eff["enabled"]:
        return {"method": "snmp", "ok": False, "skipped": True, "host": host}

    try:
        import pysnmp  # noqa: F401
    except ImportError:
        return {"method": "snmp", "ok": False, "error": "pysnmp not installed", "host": host}

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
        host,
        eff["port"] or cfg.port,
        float(cfg.timeout_sec),
        int(cfg.retries),
        creds,
        ctx,
        SYS_UPTIME_OID,
    )
    if raw is None:
        return {"method": "snmp", "ok": False, "error": "SNMP GET sysUpTime failed", "host": host}
    return {
        "method": "snmp",
        "ok": True,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "host": host,
    }


def _probe_host(db: Session, device: Device, host: str, role: str, label: str) -> dict[str, Any] | None:
    probes: list[dict[str, Any]] = []
    ports: list[tuple[str, int]] = []
    for method_label, port in (
        ("tcp_ssh", device.ssh_port or 22),
        ("tcp_netconf", device.netconf_port or 830),
    ):
        if port and not any(existing == port for _, existing in ports):
            ports.append((method_label, port))

    for method_label, port in ports:
        ok, latency_ms, error = _tcp_probe(host, port)
        probe = {"method": method_label, "port": port, "ok": ok, "host": host, "role": role, "label": label}
        if error:
            probe["error"] = error
        probes.append(probe)
        if ok:
            return {
                "reachable": True,
                "latency_ms": latency_ms,
                "method": method_label,
                "probes": probes,
                "mgmt_ip_active": host,
                "mgmt_ip_active_role": role,
                "mgmt_ip_active_label": label,
            }

    snmp_probe = _snmp_probe(db, device, host)
    if not snmp_probe.get("skipped"):
        snmp_probe["role"] = role
        snmp_probe["label"] = label
        probes.append(snmp_probe)
    if snmp_probe.get("ok"):
        return {
            "reachable": True,
            "latency_ms": snmp_probe.get("latency_ms"),
            "method": "snmp",
            "probes": probes,
            "mgmt_ip_active": host,
            "mgmt_ip_active_role": role,
            "mgmt_ip_active_label": label,
        }

    return {"reachable": False, "probes": probes, "mgmt_ip_active": host, "mgmt_ip_active_role": role, "mgmt_ip_active_label": label}


def format_unreachable_detail(device: Device, probe: dict[str, Any] | None = None) -> str:
    """Human-readable summary listing each management IP that was tried."""
    candidates = (probe or {}).get("mgmt_ip_candidates") or mgmt_ip_candidates(device)
    parts: list[str] = []
    for cand in candidates:
        label = cand.get("label") or cand.get("role") or "管理"
        parts.append(f"{label} {cand['ip']}")
    tried = "、".join(parts) if parts else device.mgmt_ip
    return f"设备管理面不可达（已尝试 {tried}）"


def persist_active_endpoint(
    device: Device,
    host: str,
    role: str,
    *,
    method: str = "snmp",
    latency_ms: float | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    device.mgmt_ip_active = host
    device.mgmt_ip_active_role = role
    device.last_reachability_at = now
    device.last_reachability_latency_ms = latency_ms
    device.last_reachability_method = method


def ensure_reachable_mgmt_ip(
    db: Session,
    device: Device,
    *,
    persist: bool = True,
) -> dict[str, Any]:
    """Probe primary then backup; raise if neither is reachable."""
    result = probe_reachability(db, device, persist=persist)
    if not result.get("reachable"):
        raise MgmtUnreachableError(format_unreachable_detail(device, result), probe=result)
    return result


def ensure_snmp_mgmt_ip(
    db: Session,
    device: Device,
    *,
    persist: bool = True,
) -> str:
    """Return a management IP that answers SNMP; fall back to TCP reachability probe."""
    from app.services import snmp_device, snmp_settings as snmp_cfg

    cfg = snmp_cfg.get_or_create(db)
    eff = snmp_device.effective_snmp(device, cfg)
    if not cfg.enabled or not eff["enabled"]:
        return device.active_mgmt_ip

    candidates = mgmt_ip_candidates(device)
    ordered: list[dict[str, str]] = []
    if device.mgmt_ip_active:
        active = next((c for c in candidates if c["ip"] == device.mgmt_ip_active), None)
        if active:
            ordered.append(active)
    for cand in candidates:
        if cand not in ordered:
            ordered.append(cand)

    for cand in ordered:
        snmp_probe = _snmp_probe(db, device, cand["ip"])
        if snmp_probe.get("ok"):
            if persist:
                persist_active_endpoint(
                    device,
                    cand["ip"],
                    cand["role"],
                    method="snmp",
                    latency_ms=snmp_probe.get("latency_ms"),
                )
            return cand["ip"]

    result = probe_reachability(db, device, persist=persist)
    if result.get("reachable") and result.get("mgmt_ip_active"):
        return str(result["mgmt_ip_active"])

    raise MgmtUnreachableError(format_unreachable_detail(device, result), probe=result)


def _persist_reachability(device: Device, result: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc)
    if result.get("reachable"):
        device.mgmt_ip_active = result.get("mgmt_ip_active")
        device.mgmt_ip_active_role = result.get("mgmt_ip_active_role")
        device.last_reachability_at = now
        device.last_reachability_latency_ms = result.get("latency_ms")
        device.last_reachability_method = result.get("method")
    else:
        device.last_reachability_at = now
        device.last_reachability_latency_ms = None
        device.last_reachability_method = None


def probe_reachability(db: Session, device: Device, *, persist: bool = True) -> dict[str, Any]:
    """Try primary then backup management IP; persist active endpoint on device."""
    all_probes: list[dict[str, Any]] = []
    candidates = mgmt_ip_candidates(device)

    for cand in candidates:
        attempt = _probe_host(db, device, cand["ip"], cand["role"], cand["label"])
        if not attempt:
            continue
        all_probes.extend(attempt.get("probes") or [])
        if attempt.get("reachable"):
            result = {
                **attempt,
                "probes": all_probes,
                "dry_run": settings.dry_run,
                "mgmt_ip_candidates": candidates,
            }
            if persist:
                _persist_reachability(device, result)
            return result

    result = {
        "reachable": False,
        "latency_ms": None,
        "method": None,
        "probes": all_probes,
        "dry_run": settings.dry_run,
        "mgmt_ip_active": device.mgmt_ip_active,
        "mgmt_ip_active_role": device.mgmt_ip_active_role,
        "mgmt_ip_candidates": candidates,
    }
    if persist:
        _persist_reachability(device, result)
    return result


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
        "mgmt_ip_primary_label": "管理网",
        "mgmt_ip_backup_label": "公网",
    }
