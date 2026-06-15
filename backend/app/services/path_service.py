"""Circuit path computation: SR explicit paths vs BGP EVPN/OSPF auto."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit, CircuitEndpoint, CircuitPathHop
from app.models.device import Device
from app.models.enums import OverlayTech, PathMode
from app.models.link import Link


@dataclass
class PathHopOut:
    device_id: int
    name: str
    role: str
    overlay_tech: str
    sr_node_sid: int | None
    hop_type: str  # endpoint | via | auto

    def as_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "role": self.role,
            "overlay_tech": self.overlay_tech,
            "sr_node_sid": self.sr_node_sid,
            "hop_type": self.hop_type,
        }


VXLAN_LIMITATION = (
    "BGP EVPN + OSPF 底层为 IGP 最短路径选路，无法指定经由设备；"
    "流量按 OSPF cost 自动转发。"
)


def _device_row(db: Session, device_id: int) -> Device | None:
    return db.get(Device, device_id)


def _hop_from_device(device: Device, hop_type: str) -> PathHopOut:
    return PathHopOut(
        device_id=device.id,
        name=device.name,
        role=device.role.value,
        overlay_tech=device.overlay_tech.value,
        sr_node_sid=device.sr_node_sid,
        hop_type=hop_type,
    )


def ordered_endpoint_devices(circuit: Circuit) -> list[Device]:
    """Return endpoint devices in A→Z order."""
    eps = sorted(circuit.endpoints, key=lambda e: (e.label != "A", e.label, e.id))
    return [ep.device for ep in eps if ep.device]


def endpoint_device_ids_from_list(endpoint_ids: list[int]) -> list[int]:
    return endpoint_ids


def _link_graph(db: Session) -> dict[int, set[int]]:
    graph: dict[int, set[int]] = {}
    for link in db.execute(select(Link)).scalars().all():
        graph.setdefault(link.device_a_id, set()).add(link.device_z_id)
        graph.setdefault(link.device_z_id, set()).add(link.device_a_id)
    return graph


def _has_link(db: Session, a_id: int, b_id: int) -> bool:
    if a_id == b_id:
        return True
    row = db.execute(
        select(Link.id).where(
            or_(
                (Link.device_a_id == a_id) & (Link.device_z_id == b_id),
                (Link.device_a_id == b_id) & (Link.device_z_id == a_id),
            )
        )
    ).first()
    return row is not None


def shortest_path(db: Session, start_id: int, end_id: int) -> list[int] | None:
    if start_id == end_id:
        return [start_id]
    graph = _link_graph(db)
    queue: deque[list[int]] = deque([[start_id]])
    seen = {start_id}
    while queue:
        path = queue.popleft()
        node = path[-1]
        for nxt in graph.get(node, ()):
            if nxt in seen:
                continue
            npath = path + [nxt]
            if nxt == end_id:
                return npath
            seen.add(nxt)
            queue.append(npath)
    return None


def supports_explicit_sr(devices: list[Device]) -> tuple[bool, str | None]:
    if not devices:
        return False, "缺少端点设备"
    if any(d.overlay_tech == OverlayTech.VXLAN_EVPN for d in devices):
        return False, VXLAN_LIMITATION
    if any(d.overlay_tech != OverlayTech.SRMPLS_EVPN for d in devices):
        return False, "路径中存在非 SR-MPLS 设备，无法建立显式 SR 路径"
    missing = [d.name for d in devices if not d.sr_node_sid]
    if missing:
        return False, f"以下 SR 设备未配置 Node SID: {', '.join(missing)}"
    return True, None


def build_device_chain(
    db: Session,
    endpoint_ids: list[int],
    via_ids: list[int] | None = None,
    path_mode: PathMode = PathMode.AUTO,
) -> list[Device]:
    if len(endpoint_ids) < 2:
        devices = [_device_row(db, i) for i in endpoint_ids]
        return [d for d in devices if d]
    a_id, z_id = endpoint_ids[0], endpoint_ids[-1]
    if path_mode == PathMode.EXPLICIT_SR and via_ids:
        chain_ids = [a_id, *via_ids, z_id]
        out: list[Device] = []
        for did in chain_ids:
            if out and out[-1].id == did:
                continue
            dev = _device_row(db, did)
            if dev:
                out.append(dev)
        return out
    auto = shortest_path(db, a_id, z_id)
    if auto:
        return [d for i in auto if (d := _device_row(db, i))]
    return [d for i in (a_id, z_id) if (d := _device_row(db, i))]


def segment_list(devices: list[Device]) -> list[int]:
    sids: list[int] = []
    for d in devices:
        if d.sr_node_sid and (not sids or sids[-1] != d.sr_node_sid):
            sids.append(d.sr_node_sid)
    return sids


def validate_connectivity(db: Session, device_ids: list[int]) -> list[str]:
    errors: list[str] = []
    for i in range(len(device_ids) - 1):
        a, b = device_ids[i], device_ids[i + 1]
        if not _has_link(db, a, b):
            da, db_ = _device_row(db, a), _device_row(db, b)
            errors.append(
                f"{da.name if da else a} 与 {db_.name if db_ else b} 之间无骨干链路"
            )
    return errors


def preview_path(
    db: Session,
    endpoint_ids: list[int],
    via_ids: list[int] | None = None,
    path_mode: PathMode = PathMode.AUTO,
) -> dict:
    via_ids = via_ids or []
    endpoints = [_device_row(db, i) for i in endpoint_ids]
    endpoints = [d for d in endpoints if d]
    all_involved = list(
        dict.fromkeys(
            endpoint_ids + via_ids
        )
    )
    involved_devices = [d for i in all_involved if (d := _device_row(db, i))]

    explicit_ok, reason = supports_explicit_sr(involved_devices)
    effective_mode = path_mode
    if path_mode == PathMode.EXPLICIT_SR and not explicit_ok:
        return {
            "path_mode": path_mode.value,
            "explicit_supported": False,
            "reason": reason,
            "hops": [],
            "segment_list": [],
            "connectivity_errors": [],
        }

    if path_mode == PathMode.EXPLICIT_SR:
        chain = build_device_chain(db, endpoint_ids, via_ids, PathMode.EXPLICIT_SR)
        if len(chain) <= 1:
            hop_types = ["endpoint"] * len(chain)
        elif len(chain) == 2:
            hop_types = ["endpoint", "endpoint"]
        else:
            hop_types = ["endpoint"] + ["via"] * (len(chain) - 2) + ["endpoint"]
    else:
        chain = build_device_chain(db, endpoint_ids, None, PathMode.AUTO)
        hop_types = ["auto"] * len(chain)
        if any(d.overlay_tech == OverlayTech.VXLAN_EVPN for d in chain):
            reason = reason or VXLAN_LIMITATION
        elif all(d.overlay_tech == OverlayTech.SRMPLS_EVPN for d in chain):
            reason = "SR-MPLS 未指定经由设备时将按 IS-IS SR 最短路径转发（auto）"

    hops = [
        _hop_from_device(d, hop_types[i] if i < len(hop_types) else "auto").as_dict()
        for i, d in enumerate(chain)
    ]
    conn_errors = validate_connectivity(db, [d.id for d in chain])
    segs = segment_list(chain) if explicit_ok or all(
        d.overlay_tech == OverlayTech.SRMPLS_EVPN for d in chain
    ) else []

    return {
        "path_mode": effective_mode.value,
        "explicit_supported": explicit_ok,
        "reason": reason,
        "hops": hops,
        "segment_list": segs,
        "connectivity_errors": conn_errors,
    }


def full_path_for_circuit(db: Session, circuit: Circuit) -> list[Device]:
    endpoint_ids = [ep.device_id for ep in sorted(
        circuit.endpoints, key=lambda e: (e.label != "A", e.label, e.id)
    )]
    via_ids = [h.device_id for h in sorted(circuit.path_hops, key=lambda h: h.sequence)]
    return build_device_chain(db, endpoint_ids, via_ids, circuit.path_mode)


def save_path_hops(db: Session, circuit: Circuit, via_device_ids: list[int]) -> None:
    for hop in list(circuit.path_hops):
        db.delete(hop)
    db.flush()
    for seq, device_id in enumerate(via_device_ids):
        db.add(CircuitPathHop(circuit_id=circuit.id, device_id=device_id, sequence=seq))
    db.flush()
