"""SNMP counter polling for per-circuit traffic telemetry.

Maps circuit endpoints to device interfaces and derives Mbps from IF-MIB
HC octet counters. Returns unavailable (not fabricated) when SNMP cannot poll.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.circuit import Circuit, CircuitEndpoint
from app.models.device import Device, DeviceInterface
from app.models.enums import CircuitStatus, Vendor
from app.models.snmp_settings import SnmpSettings
from app.services import snmp_device, snmp_settings as snmp_cfg
from app.services.mib_registry import HH3C_EVC, IF_MIB
from app.services.port_inventory import (
    huawei_physical_port,
    is_huawei_subinterface,
    parse_huawei_subinterface,
)

# cache key -> (in_octets, out_octets, monotonic_ts)
# key = (device_id, kind, ifindex, srv_inst_id) where kind is "if" | "evc"
_counter_cache: dict[tuple[int, str, int, int], tuple[int, int, float]] = {}
# device_id -> (monotonic_ts, name -> ifindex)
_ifname_index_cache: dict[int, tuple[float, dict[str, int]]] = {}
_IFNAME_CACHE_TTL_SEC = 300.0


@dataclass
class TrafficPollResult:
    rx_mbps: float
    tx_mbps: float
    utilization_pct: float
    errors: int
    tunnel_up: bool
    source: str


@dataclass(frozen=True)
class _PollTarget:
    ifindex: int
    name: str


def simulation_allowed() -> bool:
    return bool(settings.telemetry_simulation)


def endpoints_for_traffic_poll(circuit: Circuit) -> list[CircuitEndpoint]:
    """Poll customer handoff only (端点 A), not every transit PE."""
    eps = [ep for ep in circuit.endpoints if ep.device_id]
    if not eps:
        return []
    by_label = {ep.label.upper(): ep for ep in eps}
    if "A" in by_label:
        return [by_label["A"]]
    if "Z" in by_label:
        return [by_label["Z"]]
    return [sorted(eps, key=lambda e: e.label)[0]]


def _resolve_iface(
    db: Session, device_id: int, interface_name: str
) -> DeviceInterface | None:
    return db.execute(
        select(DeviceInterface).where(
            DeviceInterface.device_id == device_id,
            DeviceInterface.name == interface_name,
        )
    ).scalar_one_or_none()


def _huawei_ac_name(parent: str, svid: int) -> str:
    return f"{huawei_physical_port(parent)}.{svid}"


def _ifname_index_map(db: Session, device: Device) -> dict[str, int]:
    now = time.monotonic()
    cached = _ifname_index_cache.get(device.id)
    if cached and now - cached[0] < _IFNAME_CACHE_TTL_SEC:
        return cached[1]

    from app.services import snmp

    mapping: dict[str, int] = {}
    try:
        for row in snmp.probe_interfaces(db, device):
            name = (row.get("name") or "").strip()
            ifindex = row.get("ifindex")
            if name and ifindex is not None:
                mapping[name] = int(ifindex)
    except Exception:
        if cached:
            return cached[1]
        return {}

    _ifname_index_cache[device.id] = (now, mapping)
    return mapping


def _persist_ifindex(
    db: Session, device_id: int, name: str, ifindex: int
) -> DeviceInterface:
    iface = _resolve_iface(db, device_id, name)
    if iface is None:
        iface = DeviceInterface(
            device_id=device_id,
            name=name,
            ifindex=ifindex,
            discovered_via="snmp-subif",
        )
        db.add(iface)
    else:
        iface.ifindex = ifindex
        if not iface.discovered_via:
            iface.discovered_via = "snmp-subif"
    db.flush()
    return iface


def _resolve_poll_target(
    db: Session,
    device: Device,
    interface_name: str,
    srv_inst_id: int | None,
) -> _PollTarget | None:
    """Resolve the SNMP counter target for a circuit endpoint."""
    parsed = parse_huawei_subinterface(interface_name)
    if parsed and device.vendor == Vendor.HUAWEI:
        parent, svid = parsed
        if srv_inst_id is not None and svid != srv_inst_id:
            return None
        iface = _resolve_iface(db, device.id, interface_name)
        if iface and iface.ifindex is not None:
            return _PollTarget(iface.ifindex, iface.name)
        idx = _ifname_index_map(db, device).get(interface_name)
        if idx is not None:
            _persist_ifindex(db, device.id, interface_name, idx)
            return _PollTarget(idx, interface_name)
        return None

    if device.vendor == Vendor.HUAWEI and srv_inst_id is not None:
        if is_huawei_subinterface(interface_name):
            return None
        ac_name = _huawei_ac_name(interface_name, srv_inst_id)
        iface = _resolve_iface(db, device.id, ac_name)
        if iface and iface.ifindex is not None:
            return _PollTarget(iface.ifindex, iface.name)
        idx = _ifname_index_map(db, device).get(ac_name)
        if idx is not None:
            _persist_ifindex(db, device.id, ac_name, idx)
            return _PollTarget(idx, ac_name)
        return None

    iface = _resolve_iface(db, device.id, interface_name)
    if iface is None or iface.ifindex is None:
        idx = _ifname_index_map(db, device).get(interface_name)
        if idx is not None:
            iface = _persist_ifindex(db, device.id, interface_name, idx)
        else:
            return None
    return _PollTarget(iface.ifindex, iface.name)


def _get_oid(
    device: Device,
    oid: str,
    cfg: SnmpSettings,
    community: str,
    *,
    port: int | None = None,
) -> int | None:  # pragma: no cover
    from pysnmp.hlapi.asyncio import ContextData  # pragma: no cover

    from app.services import snmp_hlapi
    from app.services.snmp import _build_credentials

    eff = snmp_device.effective_snmp(device, cfg)
    creds = _build_credentials(device, cfg, community)
    ctx = (
        ContextData(eff["v3_context_name"])
        if eff["version"] == "3" and eff["v3_context_name"]
        else ContextData()
    )
    raw = snmp_hlapi.get_oid(
        device.active_mgmt_ip,
        port or eff["port"] or cfg.port,
        float(cfg.timeout_sec),
        int(cfg.retries),
        creds,
        ctx,
        oid,
    )
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def poll_iface_counters(
    db: Session,
    device: Device,
    iface: DeviceInterface,
    interval_sec: float,
    srv_inst_id: int | None = None,
) -> tuple[float, float, int, bool] | None:
    """Public wrapper for interface / service-instance counter polling."""
    if iface.ifindex is None:
        return None
    return _poll_iface_counters(
        db, device, _PollTarget(iface.ifindex, iface.name), interval_sec, srv_inst_id
    )


def _poll_iface_counters(
    db: Session,
    device: Device,
    target: _PollTarget,
    interval_sec: float,
    srv_inst_id: int | None = None,
) -> tuple[float, float, int, bool] | None:
    cfg = snmp_cfg.get_or_create(db)
    device_snmp = snmp_device.effective_snmp(device)
    if not cfg.enabled or not device_snmp["enabled"]:
        return None

    ifindex = target.ifindex
    community = snmp_cfg.effective_community(db, device)
    port = device_snmp["port"]
    # H3C only aggregates traffic at the physical port via standard IF-MIB; the
    # per-circuit (per Ethernet service-instance / AC) bytes must be read from
    # the H3C private HH3C-EVC-MIB, indexed by (ifIndex, serviceInstanceId).
    # Huawei (and others) expose per-AC traffic on the sub-interface's own
    # ifIndex, so the standard IF-MIB HC counters are correct for them.
    use_evc = device.vendor == Vendor.H3C and srv_inst_id is not None
    if use_evc:
        idx = HH3C_EVC.stat_index(ifindex, srv_inst_id)
        in_oid = HH3C_EVC.srvInstInBytes.column(idx)
        out_oid = HH3C_EVC.srvInstOutBytes.column(idx)
        cache_key = (device.id, "evc", ifindex, srv_inst_id)
    else:
        in_oid = IF_MIB.ifHCInOctets.column(ifindex)
        out_oid = IF_MIB.ifHCOutOctets.column(ifindex)
        cache_key = (device.id, "if", ifindex, 0)
    oper_oid = IF_MIB.ifOperStatus.column(ifindex)

    try:
        in_oct = _get_oid(device, in_oid, cfg, community, port=port)
        out_oct = _get_oid(device, out_oid, cfg, community, port=port)
        oper_raw = _get_oid(device, oper_oid, cfg, community, port=port)
    except RuntimeError:
        return None

    if in_oct is None or out_oct is None:
        return None

    oper_up = oper_raw == 1 if oper_raw is not None else True
    now = time.monotonic()
    prev = _counter_cache.get(cache_key)
    _counter_cache[cache_key] = (in_oct, out_oct, now)

    if prev is None:
        return 0.0, 0.0, 0, oper_up

    prev_in, prev_out, prev_ts = prev
    elapsed = max(now - prev_ts, interval_sec * 0.5, 1.0)
    delta_in = max(in_oct - prev_in, 0)
    delta_out = max(out_oct - prev_out, 0)
    rx = round(delta_in * 8 / elapsed / 1_000_000, 2)
    tx = round(delta_out * 8 / elapsed / 1_000_000, 2)
    return rx, tx, 0, oper_up


def _unavailable_traffic(circuit: Circuit) -> TrafficPollResult:
    up = circuit.status == CircuitStatus.ACTIVE
    return TrafficPollResult(
        rx_mbps=0.0,
        tx_mbps=0.0,
        utilization_pct=0.0,
        errors=0,
        tunnel_up=up,
        source="unavailable",
    )


def _simulate_traffic(circuit: Circuit) -> TrafficPollResult:
    """Explicit lab-only simulation — requires BUGIS_TELEMETRY_SIMULATION=true."""
    import random

    bw = max(circuit.bandwidth_mbps, 1)
    util = random.uniform(5, 85)
    tx = round(bw * util / 100.0, 2)
    rx = round(tx * random.uniform(0.6, 1.1), 2)
    up = circuit.status == CircuitStatus.ACTIVE and random.random() > 0.02
    return TrafficPollResult(
        rx_mbps=rx if up else 0.0,
        tx_mbps=tx if up else 0.0,
        utilization_pct=round(util if up else 0.0, 2),
        errors=random.randint(0, 2) if up else random.randint(1, 5),
        tunnel_up=up,
        source="simulated",
    )


def poll_circuit_traffic(
    db: Session,
    circuit: Circuit,
    *,
    interval_sec: float = 30.0,
) -> TrafficPollResult:
    """Poll SNMP counters on the customer access endpoint (A) only."""
    if simulation_allowed() and settings.dry_run:
        return _simulate_traffic(circuit)

    cfg = snmp_cfg.get_or_create(db)
    if not cfg.enabled:
        return _unavailable_traffic(circuit)

    total_rx = 0.0
    total_tx = 0.0
    total_errors = 0
    any_poll = False
    all_up = True

    for ep in endpoints_for_traffic_poll(circuit):
        device = db.get(Device, ep.device_id)
        if not device:
            continue
        srv_inst_id = ep.vlan_id or circuit.vlan_id
        target = _resolve_poll_target(db, device, ep.interface_name, srv_inst_id)
        if target is None:
            continue
        polled = _poll_iface_counters(
            db, device, target, interval_sec, srv_inst_id=srv_inst_id
        )
        if polled is None:
            continue
        any_poll = True
        rx, tx, errors, oper_up = polled
        total_rx += rx
        total_tx += tx
        total_errors += errors
        if not oper_up:
            all_up = False

    if not any_poll:
        if simulation_allowed() and settings.dry_run:
            return _simulate_traffic(circuit)
        return _unavailable_traffic(circuit)

    bw = max(circuit.bandwidth_mbps, 1)
    peak = max(total_rx, total_tx)
    util = round(peak / bw * 100, 2)
    tunnel_up = all_up and circuit.status == CircuitStatus.ACTIVE
    return TrafficPollResult(
        rx_mbps=round(total_rx, 2),
        tx_mbps=round(total_tx, 2),
        utilization_pct=util,
        errors=total_errors,
        tunnel_up=tunnel_up,
        source="snmp",
    )
