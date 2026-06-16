"""Deterministic probe fallback when platform dry_run is enabled."""
from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.models.circuit import Circuit
from app.models.enums import CircuitStatus
from app.services.circuit_probe.path import resolve_underlay_path
from app.services.circuit_probe.stats import jitter_from_rtts, summarize_rtts


def _seed(circuit: Circuit) -> float:
    digest = hashlib.sha256(f"{circuit.id}:{circuit.code}".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def simulate_probe(db: Session, circuit: Circuit) -> dict:
    """Path-aligned simulated metrics (labeled explicitly as simulated)."""
    path = resolve_underlay_path(db, circuit)
    devices = path["devices"]
    active = circuit.status == CircuitStatus.ACTIVE
    seed = _seed(circuit)

    base_rtt = 1.2 + seed * 4.0
    samples = [round(base_rtt + (seed * (i + 1)) % 1.5, 2) for i in range(5)]
    stats = summarize_rtts(samples)
    loss = 0.0 if active else round(5.0 + seed * 10, 3)
    reachable = active and loss < 50

    hops = []
    per_hop = base_rtt / max(len(devices), 1)
    cum = 0.0
    for idx, dev in enumerate(devices, start=1):
        cum = round(cum + per_hop, 2)
        hops.append({
            "hop": idx,
            "device": dev.name,
            "vendor": dev.vendor.value,
            "role": dev.role.value,
            "ip": dev.loopback_ip or dev.mgmt_ip,
            "target": None,
            "segment_rtt_ms": round(per_hop, 2),
            "rtt_ms": cum if reachable else None,
            "packet_loss_pct": loss if idx == len(devices) else 0.0,
            "status": "up" if reachable else "timeout",
            "probe_source": None,
        })

    endpoints = path["endpoints"]
    a_dev = endpoints[0] if endpoints else None
    z_dev = endpoints[-1] if len(endpoints) > 1 else None

    return {
        "circuit": circuit.code,
        "mode": "simulated",
        "probe_method": "simulated",
        "path_mode": path["path_mode"],
        "path_reason": path.get("path_reason"),
        "segment_list": path.get("segment_list") or [],
        "reachable": reachable,
        "rtt_ms": stats["avg_ms"] if reachable else None,
        "jitter_ms": stats["jitter_ms"] if reachable else 0.0,
        "packet_loss_pct": loss if reachable else 100.0,
        "hop_count": len(hops),
        "hops": hops,
        "fabric": {
            "method": "simulated",
            "samples_per_hop": 5,
            "reachable": reachable,
        },
        "service_plane": {
            "method": "simulated",
            "source_device": a_dev.name if a_dev else None,
            "target_device": z_dev.name if z_dev else None,
            "vsi_name": circuit.vsi_name,
            "vni": circuit.vni,
            "samples": len(samples),
            "rtts_ms": samples if reachable else [],
            "packet_loss_pct": loss if reachable else 100.0,
            "jitter_ms": jitter_from_rtts(samples) if reachable else 0.0,
            "reachable": reachable,
        },
    }
