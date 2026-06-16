"""Resolve underlay forwarding path (same logic as path preview)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.circuit import Circuit
from app.models.device import Device
from app.models.enums import PathMode
from app.services import path_service


def resolve_underlay_path(db: Session, circuit: Circuit) -> dict:
    """Return ordered devices + metadata aligned with path preview."""
    endpoints = path_service.ordered_endpoint_devices(circuit)
    endpoint_ids = [ep.device_id for ep in sorted(
        circuit.endpoints, key=lambda e: (e.label != "A", e.label, e.id)
    )]

    if circuit.path_mode == PathMode.EXPLICIT_SR or (circuit.path_hops and len(circuit.path_hops) > 0):
        chain = path_service.full_path_for_circuit(db, circuit)
        preview = path_service.preview_path(
            db,
            endpoint_ids,
            [h.device_id for h in sorted(circuit.path_hops, key=lambda x: x.sequence)],
            PathMode.EXPLICIT_SR,
        )
    else:
        preview = path_service.preview_path(db, endpoint_ids, None, PathMode.AUTO)
        chain = path_service.build_device_chain(db, endpoint_ids, None, PathMode.AUTO)

    hops_meta = preview.get("hops") or []
    return {
        "devices": [d for d in chain if d],
        "endpoints": endpoints,
        "path_mode": preview.get("path_mode") or (circuit.path_mode.value if circuit.path_mode else "auto"),
        "path_reason": preview.get("reason"),
        "segment_list": preview.get("segment_list") or [],
        "hops_meta": hops_meta,
    }
