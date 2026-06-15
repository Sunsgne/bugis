"""SNMP counter polling for per-circuit traffic telemetry.

Maps circuit endpoints to device interfaces and derives Mbps from IF-MIB
HC octet counters. Falls back to simulation when dry-run or SNMP is off.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.circuit import Circuit
from app.models.device import Device, DeviceInterface
from app.models.enums import CircuitStatus
from app.models.snmp_settings import SnmpSettings
from app.services import snmp_device, snmp_settings as snmp_cfg
from app.services.mib_registry import IF_MIB

# (device_id, ifindex) -> (in_octets, out_octets, monotonic_ts)
_counter_cache: dict[tuple[int, int], tuple[int, int, float]] = {}


@dataclass
class TrafficPollResult:
    rx_mbps: float
    tx_mbps: float
    utilization_pct: float
    errors: int
    tunnel_up: bool
    source: str


def _resolve_iface(
    db: Session, device_id: int, interface_name: str
) -> DeviceInterface | None:
    return db.execute(
        select(DeviceInterface).where(
            DeviceInterface.device_id == device_id,
            DeviceInterface.name == interface_name,
        )
    ).scalar_one_or_none()


def _get_oid(
    device: Device,
    oid: str,
    cfg: SnmpSettings,
    community: str,
    *,
    port: int | None = None,
) -> int | None:  # pragma: no cover
    from pysnmp.hlapi import (
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        UsmUserData,
        getCmd,
    )

    from app.services.snmp import _auth_proto, _build_credentials

    creds = _build_credentials(cfg, community)
    ctx = (
        ContextData(cfg.v3_context_name)
        if cfg.version == "3" and cfg.v3_context_name
        else ContextData()
    )
    err_ind, err_stat, _idx, var_binds = next(
        getCmd(
            SnmpEngine(),
            creds,
            UdpTransportTarget(
                (device.mgmt_ip, port or cfg.port),
                timeout=cfg.timeout_sec,
                retries=cfg.retries,
            ),
            ctx,
            ObjectType(ObjectIdentity(oid)),
        )
    )
    if err_ind or err_stat:
        return None
    for _oid, val in var_binds:
        try:
            return int(val)
        except (TypeError, ValueError):
            return None
    return None


def _poll_iface_counters(
    db: Session,
    device: Device,
    iface: DeviceInterface,
    interval_sec: float,
) -> tuple[float, float, int, bool] | None:
    cfg = snmp_cfg.get_or_create(db)
    device_snmp = snmp_device.effective_snmp(device)
    if not cfg.enabled or not device_snmp["enabled"]:
        return None

    ifindex = iface.ifindex
    if ifindex is None:
        return None

    community = snmp_cfg.effective_community(db, device)
    port = device_snmp["port"]
    in_oid = IF_MIB.ifHCInOctets.column(ifindex)
    out_oid = IF_MIB.ifHCOutOctets.column(ifindex)
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
    key = (device.id, ifindex)
    now = time.monotonic()
    prev = _counter_cache.get(key)
    _counter_cache[key] = (in_oct, out_oct, now)

    if prev is None:
        return 0.0, 0.0, 0, oper_up

    prev_in, prev_out, prev_ts = prev
    elapsed = max(now - prev_ts, interval_sec * 0.5, 1.0)
    delta_in = max(in_oct - prev_in, 0)
    delta_out = max(out_oct - prev_out, 0)
    rx = round(delta_in * 8 / elapsed / 1_000_000, 2)
    tx = round(delta_out * 8 / elapsed / 1_000_000, 2)
    return rx, tx, 0, oper_up


def _simulate_traffic(circuit: Circuit) -> TrafficPollResult:
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
        source="snmp-sim",
    )


def poll_circuit_traffic(
    db: Session,
    circuit: Circuit,
    *,
    interval_sec: float = 30.0,
) -> TrafficPollResult:
    """Poll SNMP counters on circuit endpoints and aggregate traffic."""
    if settings.dry_run:
        return _simulate_traffic(circuit)

    cfg = snmp_cfg.get_or_create(db)
    if not cfg.enabled:
        return _simulate_traffic(circuit)

    total_rx = 0.0
    total_tx = 0.0
    total_errors = 0
    any_poll = False
    all_up = True

    for ep in circuit.endpoints:
        if not ep.device_id:
            continue
        device = db.get(Device, ep.device_id)
        if not device:
            continue
        iface = _resolve_iface(db, ep.device_id, ep.interface_name)
        if iface is None:
            continue
        polled = _poll_iface_counters(db, device, iface, interval_sec)
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
        return _simulate_traffic(circuit)

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
