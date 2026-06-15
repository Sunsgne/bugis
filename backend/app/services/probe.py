"""Active circuit path probe (on-demand connectivity test).

Simulates an end-to-end probe (ping/TWAMP-style) across a circuit's endpoints,
computing a per-hop path with cumulative latency and loss. Results are recorded
as a telemetry sample so on-demand tests also feed SLA history.

In a live deployment this would trigger TWAMP/Y.1731/ping on the devices.
"""
from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit
from app.models.device import Device
from app.models.enums import CircuitStatus, DeviceRole, PathMode
from app.services import path_service, telemetry_service


def _path_devices(db: Session, circuit: Circuit) -> list[Device]:
    """Ordered device path: explicit SR hops when configured, else heuristic."""
    if circuit.path_mode == PathMode.EXPLICIT_SR or circuit.path_hops:
        chain = path_service.full_path_for_circuit(db, circuit)
        if chain:
            return chain

    endpoint_devices = [ep.device for ep in circuit.endpoints if ep.device]
    if len(endpoint_devices) < 2:
        return endpoint_devices

    path: list[Device] = []
    for i, dev in enumerate(endpoint_devices):
        path.append(dev)
        if i < len(endpoint_devices) - 1:
            nxt = endpoint_devices[i + 1]
            # If crossing sites, insert each side's DCI gateway.
            if dev.site_id and nxt.site_id and dev.site_id != nxt.site_id:
                for sid in (dev.site_id, nxt.site_id):
                    gw = db.execute(
                        select(Device).where(
                            Device.site_id == sid,
                            Device.role.in_([DeviceRole.DCI_GW, DeviceRole.BORDER_LEAF]),
                        )
                    ).scalars().first()
                    seen = {d.id for d in path} | {nxt.id}
                    if gw and gw.id not in seen:
                        path.append(gw)
    return path


def probe_circuit(db: Session, circuit: Circuit) -> dict:
    devices = _path_devices(db, circuit)
    active = circuit.status == CircuitStatus.ACTIVE

    # Probability the path is fully reachable (degraded for inactive circuits).
    reachable = active and random.random() > 0.05
    hops = []
    cum_latency = 0.0
    total_loss = 0.0
    down_at = random.randint(1, max(1, len(devices))) if not reachable else -1

    for idx, dev in enumerate(devices, start=1):
        hop_latency = round(random.uniform(0.4, 6.0), 2)
        hop_loss = round(random.uniform(0, 0.3), 3)
        up = reachable or idx < down_at
        if up:
            cum_latency += hop_latency
            total_loss += hop_loss
        hops.append({
            "hop": idx,
            "device": dev.name,
            "vendor": dev.vendor.value,
            "role": dev.role.value,
            "ip": dev.loopback_ip or dev.mgmt_ip,
            "rtt_ms": round(cum_latency, 2) if up else None,
            "status": "up" if up else "timeout",
        })

    rtt = round(cum_latency, 2) if reachable else None
    jitter = round(random.uniform(0.1, 2.0), 2) if reachable else 0.0
    loss = round(total_loss, 3) if reachable else 100.0

    # Record as a telemetry sample for SLA history.
    from app.services import availability_service

    sample = telemetry_service.record_sample(
        db,
        circuit_id=circuit.id,
        latency_ms=rtt or 0.0,
        jitter_ms=jitter,
        packet_loss_pct=loss,
        utilization_pct=0.0,
        tunnel_state="up" if reachable else "down",
    )
    availability_service.process_tunnel_state(
        db,
        circuit,
        tunnel_up=reachable,
        source="probe",
        at=sample.created_at,
    )

    return {
        "circuit": circuit.code,
        "reachable": reachable,
        "rtt_ms": rtt,
        "jitter_ms": jitter,
        "packet_loss_pct": loss,
        "hop_count": len(hops),
        "hops": hops,
    }
