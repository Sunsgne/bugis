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


def _is_private_ip(ip: str) -> bool:
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        a, b, _, _ = (int(x) for x in parts)
    except ValueError:
        return False
    if a == 10:
        return True
    if a == 172 and 16 <= b <= 31:
        return True
    if a == 192 and b == 168:
        return True
    return False


def snmp_ip_candidates(device: Device) -> list[dict[str, str]]:
    """SNMP probe order — Huawei CE listens on 管理网/mgt VRF, not 公网."""
    cands = mgmt_ip_candidates(device)
    if device.vendor != Vendor.HUAWEI or len(cands) < 2:
        return cands

    def rank(c: dict[str, str]) -> tuple[int, int, int]:
        label = c.get("label") or ""
        ip_rank = 0 if _is_private_ip(c["ip"]) else 1
        label_rank = 0 if "管理" in label else (1 if "公网" in label else 2)
        role_rank = 0 if c["role"] == "primary" else 1
        return (label_rank, ip_rank, role_rank)

    return sorted(cands, key=rank)


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


def _snmp_probe(
    db: Session | None,
    device: Device,
    host: str,
    *,
    port: int | None = None,
) -> dict[str, Any]:
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
    walk_port = port or eff["port"] or cfg.port
    started = time.perf_counter()
    raw = snmp_hlapi.get_oid(
        host,
        walk_port,
        float(cfg.timeout_sec),
        int(cfg.retries),
        creds,
        ctx,
        SYS_UPTIME_OID,
    )
    if raw is None:
        return {
            "method": "snmp",
            "ok": False,
            "error": "SNMP GET sysUpTime failed",
            "host": host,
            "port": walk_port,
        }
    return {
        "method": "snmp",
        "ok": True,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "host": host,
        "port": walk_port,
    }


def snmp_ports_to_try(device: Device, cfg, eff: dict) -> list[int]:
    """Candidate UDP ports — Huawei CE often uses 16161 instead of 161."""
    ports: list[int] = []
    if device.vendor == Vendor.HUAWEI:
        for p in (16161, eff.get("port"), cfg.port, 161):
            if p and int(p) not in ports:
                ports.append(int(p))
        return ports
    for p in (eff.get("port"), cfg.port, 161):
        if p and int(p) not in ports:
            ports.append(int(p))
    return ports


def resolve_snmp_endpoint(
    db: Session,
    device: Device,
    *,
    persist: bool = True,
) -> tuple[str, int, dict[str, str]]:
    """Find (host, port) where SNMP sysUpTime answers — tries all mgmt IPs and ports."""
    from app.services import snmp_device, snmp_settings as snmp_cfg

    cfg = snmp_cfg.get_or_create(db)
    eff = snmp_device.effective_snmp(device, cfg)
    if not cfg.enabled or not eff["enabled"]:
        raise MgmtUnreachableError("SNMP 采集未启用（平台或设备已关闭）")

    ports = snmp_ports_to_try(device, cfg, eff)
    errors: list[str] = []
    for cand in snmp_ip_candidates(device):
        for port in ports:
            probe = _snmp_probe(db, device, cand["ip"], port=port)
            if probe.get("skipped"):
                continue
            if probe.get("ok"):
                if persist:
                    persist_active_endpoint(
                        device,
                        cand["ip"],
                        cand["role"],
                        method="snmp",
                        latency_ms=probe.get("latency_ms"),
                    )
                return cand["ip"], port, cand
            err = probe.get("error") or "SNMP 不可达"
            errors.append(f"{cand['label']} {cand['ip']}:{port} {err}")

    detail = "；".join(errors) if errors else "请检查 Community、端口（华为常见 16161）与网络可达性"
    hint = ""
    if device.vendor == Vendor.HUAWEI and device.mgmt_ip_backup:
        hint = "。华为 SNMP 通常在管理网/mgt VRF（UDP 16161），公网 IP 一般不通 SNMP；请确认主管理 IP 填管理网、备 IP 填公网，且平台能路由到管理网"
    raise MgmtUnreachableError(f"SNMP 不可达（{detail}）{hint}")


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

    snmp_ports: list[int | None] = [None]
    if db is not None:
        from app.services import snmp_device, snmp_settings as snmp_cfg

        cfg = snmp_cfg.get_or_create(db)
        eff = snmp_device.effective_snmp(device, cfg)
        if cfg.enabled and eff["enabled"]:
            snmp_ports = snmp_ports_to_try(device, cfg, eff)

    snmp_ok: dict[str, Any] | None = None
    for walk_port in snmp_ports:
        snmp_probe = _snmp_probe(db, device, host, port=walk_port)
        if not snmp_probe.get("skipped"):
            snmp_probe["role"] = role
            snmp_probe["label"] = label
            probes.append(snmp_probe)
        if snmp_probe.get("ok"):
            snmp_ok = snmp_probe
            break
    if snmp_ok:
        return {
            "reachable": True,
            "latency_ms": snmp_ok.get("latency_ms"),
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

    try:
        host, _port, _cand = resolve_snmp_endpoint(db, device, persist=persist)
        return host
    except MgmtUnreachableError:
        pass

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

    if settings.dry_run and candidates:
        first = candidates[0]
        result = {
            "reachable": True,
            "latency_ms": 1.0,
            "method": "dry_run",
            "probes": all_probes,
            "dry_run": True,
            "mgmt_ip_active": first["ip"],
            "mgmt_ip_active_role": first["role"],
            "mgmt_ip_active_label": first["label"],
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
