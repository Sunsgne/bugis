"""Orchestrate fabric + EVPN service-plane circuit probes."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.circuit import Circuit
from app.models.device import Device
from app.models.enums import CircuitStatus, ServiceType, Vendor
from app.services import availability_service, telemetry_service
from app.services.circuit_probe.cli import (
    can_run_live,
    h3c_mac_lookup_command,
    h3c_vni_ping_command,
    h3c_vsi_mac_ping_command,
    huawei_vni_ping_command,
    ping_command,
    run_cli,
)
from app.services.circuit_probe.parsers import parse_h3c_remote_mac, parse_ping_output
from app.services.circuit_probe.path import resolve_underlay_path
from app.services.circuit_probe.simulate import simulate_probe
from app.services.circuit_probe.stats import jitter_from_rtts, packet_loss_pct, summarize_rtts

logger = logging.getLogger(__name__)

PING_COUNT = 5
PING_INTERVAL_MS = 200


def _device_ip(device: Device) -> str | None:
    return device.loopback_ip or device.active_mgmt_ip


def _hop_row(
    idx: int,
    dev: Device,
    *,
    target: str | None,
    segment_rtt: float | None,
    cum_rtt: float | None,
    loss: float,
    status: str,
    probe_source: str | None,
) -> dict[str, Any]:
    return {
        "hop": idx,
        "device": dev.name,
        "vendor": dev.vendor.value,
        "role": dev.role.value,
        "ip": _device_ip(dev),
        "target": target,
        "segment_rtt_ms": segment_rtt,
        "rtt_ms": cum_rtt,
        "packet_loss_pct": loss,
        "status": status,
        "probe_source": probe_source,
    }


def _run_ping(device: Device, command: str) -> dict[str, Any]:
    try:
        output = run_cli(device, command)
        parsed = parse_ping_output(output)
        return {"ok": True, "command": command, "output": output, **parsed}
    except Exception as exc:  # noqa: BLE001 — surface southbound errors to API
        logger.warning("probe ping failed on %s: %s", device.name, exc)
        return {
            "ok": False,
            "command": command,
            "error": str(exc),
            "rtts_ms": [],
            "sent": PING_COUNT,
            "received": 0,
            "loss_pct": 100.0,
        }


def probe_fabric_hops(devices: list[Device]) -> tuple[list[dict], dict]:
    """Ping loopback-to-loopback along the resolved underlay path."""
    hops: list[dict] = []
    cum_rtt = 0.0
    fabric_ok = True
    last_loss = 0.0

    if not devices:
        return hops, {"method": "fabric_loopback", "reachable": False, "samples_per_hop": PING_COUNT}

    for i, dev in enumerate(devices):
        if i < len(devices) - 1:
            nxt = devices[i + 1]
            target = _device_ip(nxt)
            if not target or not can_run_live(dev):
                fabric_ok = False
                hops.append(_hop_row(
                    i + 1, dev,
                    target=target,
                    segment_rtt=None,
                    cum_rtt=None,
                    loss=100.0,
                    status="timeout",
                    probe_source=dev.name,
                ))
                continue

            cmd = ping_command(dev, target, count=PING_COUNT, interval_ms=PING_INTERVAL_MS)
            result = _run_ping(dev, cmd)
            if result["ok"] and result["rtts_ms"]:
                seg = round(result["rtts_ms"][-1], 2)
                cum_rtt = round(cum_rtt + seg, 2)
                last_loss = float(result.get("loss_pct") or 0.0)
                hops.append(_hop_row(
                    i + 1, dev,
                    target=target,
                    segment_rtt=seg,
                    cum_rtt=cum_rtt,
                    loss=last_loss,
                    status="up",
                    probe_source=dev.name,
                ))
            else:
                fabric_ok = False
                last_loss = 100.0
                hops.append(_hop_row(
                    i + 1, dev,
                    target=target,
                    segment_rtt=None,
                    cum_rtt=None,
                    loss=100.0,
                    status="timeout",
                    probe_source=dev.name,
                ))
        else:
            hops.append(_hop_row(
                i + 1, dev,
                target=None,
                segment_rtt=None,
                cum_rtt=round(cum_rtt, 2) if fabric_ok else None,
                loss=last_loss,
                status="up" if fabric_ok else "timeout",
                probe_source=devices[0].name if devices else None,
            ))

    return hops, {
        "method": "fabric_loopback",
        "samples_per_hop": PING_COUNT,
        "reachable": fabric_ok,
    }


def _ordered_endpoints(circuit: Circuit) -> tuple[Device | None, Device | None]:
    eps = sorted(circuit.endpoints, key=lambda e: (e.label != "A", e.label, e.id))
    a = eps[0].device if eps else None
    z = eps[-1].device if len(eps) > 1 else None
    return a, z


def probe_h3c_vsi_mac(a: Device, z: Device, circuit: Circuit) -> dict[str, Any] | None:
    """H3C L2 EVPN: resolve remote MAC on Z, ping vsi mac on A."""
    if not circuit.vsi_name or not can_run_live(a) or not can_run_live(z):
        return None
    mac_cmd = h3c_mac_lookup_command(circuit.vsi_name)
    mac_out = run_cli(z, mac_cmd)
    mac = parse_h3c_remote_mac(mac_out)
    if not mac:
        return None
    ping_cmd = h3c_vsi_mac_ping_command(circuit.vsi_name, mac, count=PING_COUNT)
    result = _run_ping(a, ping_cmd)
    return {
        "method": "h3c_vsi_mac",
        "source_device": a.name,
        "target_device": z.name,
        "vsi_name": circuit.vsi_name,
        "vni": circuit.vni,
        "remote_mac": mac,
        "command": ping_cmd,
        **result,
    }


def probe_vni_ping(a: Device, z: Device, circuit: Circuit) -> dict[str, Any] | None:
    """Overlay VNI ping A→Z VTEP loopback."""
    if circuit.vni is None:
        return None
    z_ip = _device_ip(z)
    if not z_ip or not can_run_live(a):
        return None
    if a.vendor == Vendor.H3C:
        cmd = h3c_vni_ping_command(circuit.vni, z_ip, count=PING_COUNT)
    elif a.vendor == Vendor.HUAWEI:
        cmd = huawei_vni_ping_command(circuit.vni, z_ip, count=PING_COUNT)
    else:
        cmd = ping_command(a, z_ip, count=PING_COUNT, interval_ms=PING_INTERVAL_MS)
    result = _run_ping(a, cmd)
    return {
        "method": "vni_ping" if a.vendor in (Vendor.H3C, Vendor.HUAWEI) else "underlay_ip",
        "source_device": a.name,
        "target_device": z.name,
        "vsi_name": circuit.vsi_name,
        "vni": circuit.vni,
        "target_ip": z_ip,
        "command": cmd,
        **result,
    }


def probe_service_plane(db: Session, circuit: Circuit) -> dict[str, Any]:
    """End-to-end service-plane probe from A to Z."""
    a, z = _ordered_endpoints(circuit)
    empty: dict[str, Any] = {
        "method": None,
        "source_device": a.name if a else None,
        "target_device": z.name if z else None,
        "vsi_name": circuit.vsi_name,
        "vni": circuit.vni,
        "samples": 0,
        "rtts_ms": [],
        "packet_loss_pct": 100.0,
        "jitter_ms": 0.0,
        "reachable": False,
    }
    if not a or not z:
        empty["error"] = "missing endpoints"
        return empty

    result: dict[str, Any] | None = None
    if circuit.service_type == ServiceType.L2VPN_EVPN and a.vendor == Vendor.H3C:
        try:
            result = probe_h3c_vsi_mac(a, z, circuit)
        except Exception as exc:  # noqa: BLE001
            logger.warning("H3C VSI MAC probe failed: %s", exc)
            empty["error"] = str(exc)

    if result is None:
        try:
            result = probe_vni_ping(a, z, circuit)
        except Exception as exc:  # noqa: BLE001
            logger.warning("VNI ping probe failed: %s", exc)
            if "error" not in empty:
                empty["error"] = str(exc)

    if result is None:
        return empty

    rtts = result.get("rtts_ms") or []
    stats = summarize_rtts(rtts)
    sent = int(result.get("sent") or PING_COUNT)
    received = int(result.get("received") or len(rtts))
    loss = float(result.get("loss_pct") if result.get("loss_pct") is not None else packet_loss_pct(sent, received))
    ok = bool(result.get("ok")) and loss < 100.0 and bool(rtts)

    return {
        "method": result.get("method"),
        "source_device": result.get("source_device"),
        "target_device": result.get("target_device"),
        "vsi_name": circuit.vsi_name,
        "vni": circuit.vni,
        "remote_mac": result.get("remote_mac"),
        "target_ip": result.get("target_ip"),
        "command": result.get("command"),
        "samples": len(rtts),
        "rtts_ms": rtts,
        "packet_loss_pct": loss,
        "jitter_ms": stats["jitter_ms"],
        "rtt_ms": stats["avg_ms"] if rtts else None,
        "reachable": ok,
        "error": result.get("error"),
    }


def _record_sample(db: Session, circuit: Circuit, *, reachable: bool, rtt: float | None, jitter: float, loss: float) -> None:
    sample = telemetry_service.record_sample(
        db,
        circuit_id=circuit.id,
        latency_ms=rtt or 0.0,
        jitter_ms=jitter,
        packet_loss_pct=loss,
        utilization_pct=0.0,
        tunnel_state="up" if reachable else "down",
        source="probe",
    )
    availability_service.process_tunnel_state(
        db,
        circuit,
        tunnel_up=reachable,
        source="probe",
        at=sample.created_at,
    )


def probe_circuit(db: Session, circuit: Circuit) -> dict:
    """Run path-aligned fabric + service-plane probe."""
    if settings.dry_run:
        result = simulate_probe(db, circuit)
        _record_sample(
            db, circuit,
            reachable=result["reachable"],
            rtt=result.get("rtt_ms"),
            jitter=result.get("jitter_ms") or 0.0,
            loss=result.get("packet_loss_pct") or 100.0,
        )
        return result

    if circuit.status != CircuitStatus.ACTIVE:
        return {
            "circuit": circuit.code,
            "mode": "unavailable",
            "probe_method": None,
            "reachable": False,
            "error": f"专线状态为 {circuit.status.value}，仅 active 专线可实测",
            "hop_count": 0,
            "hops": [],
        }

    path = resolve_underlay_path(db, circuit)
    devices = path["devices"]
    a, z = _ordered_endpoints(circuit)

    hops, fabric = probe_fabric_hops(devices)
    service = probe_service_plane(db, circuit)

    # Prefer service-plane e2e metrics; fall back to fabric cumulative RTT.
    e2e_rtts = service.get("rtts_ms") or []
    if e2e_rtts:
        e2e_stats = summarize_rtts(e2e_rtts)
        rtt = e2e_stats["avg_ms"]
        jitter = e2e_stats["jitter_ms"]
        loss = float(service.get("packet_loss_pct") or 0.0)
        reachable = bool(service.get("reachable"))
        probe_method = service.get("method") or "service_plane"
    else:
        up_hops = [h for h in hops if h.get("status") == "up" and h.get("rtt_ms") is not None]
        rtt = up_hops[-1]["rtt_ms"] if up_hops else None
        jitter = 0.0
        loss = float(up_hops[-1]["packet_loss_pct"]) if up_hops else 100.0
        reachable = bool(fabric.get("reachable"))
        probe_method = fabric.get("method") or "fabric_loopback"

    result = {
        "circuit": circuit.code,
        "mode": "live",
        "probe_method": probe_method,
        "path_mode": path["path_mode"],
        "path_reason": path.get("path_reason"),
        "segment_list": path.get("segment_list") or [],
        "reachable": reachable,
        "rtt_ms": rtt,
        "jitter_ms": jitter,
        "packet_loss_pct": loss,
        "hop_count": len(hops),
        "hops": hops,
        "fabric": fabric,
        "service_plane": service,
    }

    _record_sample(db, circuit, reachable=reachable, rtt=rtt, jitter=jitter, loss=loss)
    return result
