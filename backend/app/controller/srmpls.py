"""SR-MPLS EVPN control-plane extensions for the Bugis controller."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.circuit import CircuitEndpoint
from app.models.controlplane import EvpnRoute
from app.models.device import Device
from app.models.enums import EvpnEncap, OverlayTech


def _mpls_label(vni: int, device_id: int) -> int:
    # Deterministic per-(vni, device) label in dynamic range.
    return 16000 + (vni % 4000) + (device_id % 100)


def enrich_routes(
    db: Session,
    routes: list[EvpnRoute],
    endpoints: list[CircuitEndpoint],
    circuit=None,
) -> int:
    """Add MPLS encapsulation metadata for SR-MPLS capable devices."""
    mpls_devices = {
        ep.device_id
        for ep in endpoints
        if ep.device and ep.device.overlay_tech == OverlayTech.SRMPLS_EVPN
    }
    if not mpls_devices:
        return 0
    count = 0
    path_segments: list[int] = []
    if circuit is not None:
        from app.services import path_service

        path_segments = path_service.segment_list(
            path_service.full_path_for_circuit(db, circuit)
        )
    for route in routes:
        if route.origin_device_id not in mpls_devices:
            continue
        device = db.get(Device, route.origin_device_id)
        route.encap = EvpnEncap.MPLS
        route.mpls_label = _mpls_label(route.vni, route.origin_device_id or 0)
        if device and device.sr_node_sid:
            route.sr_sid = device.sr_node_sid
        if path_segments and route.origin_device_id == endpoints[0].device_id:
            route.sr_sid = path_segments[0]
        count += 1
    db.flush()
    return count
