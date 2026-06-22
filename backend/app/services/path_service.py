"""Circuit path computation: SR explicit paths vs BGP EVPN/OSPF auto."""
from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit, CircuitEndpoint, CircuitPathHop
from app.models.device import Device
from app.models.enums import OverlayTech, PathMode
from app.models.link import Link
from app.services import igp_cost_service

DEFAULT_IGP_COST = igp_cost_service.DEFAULT_IGP_COST


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


def _all_links(db: Session) -> list[Link]:
    return list(db.execute(select(Link)).scalars().all())


def _link_graph(db: Session) -> dict[int, set[int]]:
    graph: dict[int, set[int]] = {}
    for link in _all_links(db):
        graph.setdefault(link.device_a_id, set()).add(link.device_z_id)
        graph.setdefault(link.device_z_id, set()).add(link.device_a_id)
    return graph


def _links_for_pair(db: Session) -> dict[frozenset[int], Link]:
    out: dict[frozenset[int], Link] = {}
    for link in _all_links(db):
        out[frozenset({link.device_a_id, link.device_z_id})] = link
    return out


def _find_link(db: Session, a_id: int, b_id: int) -> Link | None:
    return db.execute(
        select(Link).where(
            or_(
                (Link.device_a_id == a_id) & (Link.device_z_id == b_id),
                (Link.device_a_id == b_id) & (Link.device_z_id == a_id),
            )
        )
    ).scalar_one_or_none()


def _has_link(db: Session, a_id: int, b_id: int) -> bool:
    if a_id == b_id:
        return True
    return _find_link(db, a_id, b_id) is not None


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


def shortest_path_weighted(
    db: Session,
    start_id: int,
    end_id: int,
    *,
    cost_cache: dict[int, dict[str, int]] | None = None,
) -> tuple[list[int] | None, float, str]:
    """Dijkstra over Link graph using learned IGP interface costs."""
    if start_id == end_id:
        return [start_id], 0.0, "dijkstra_igp_cost"

    links = _all_links(db)
    if cost_cache is None:
        device_ids = {start_id, end_id}
        for link in links:
            device_ids.add(link.device_a_id)
            device_ids.add(link.device_z_id)
        cost_cache = igp_cost_service.build_cost_cache(db, device_ids)

    adj: dict[int, list[tuple[int, float, int]]] = {}
    for link in links:
        cost_ab, _, _ = igp_cost_service.link_transit_cost(
            db, link, link.device_a_id, cost_cache=cost_cache
        )
        cost_ba, _, _ = igp_cost_service.link_transit_cost(
            db, link, link.device_z_id, cost_cache=cost_cache
        )
        adj.setdefault(link.device_a_id, []).append((link.device_z_id, float(cost_ab), link.id))
        adj.setdefault(link.device_z_id, []).append((link.device_a_id, float(cost_ba), link.id))

    dist: dict[int, float] = {start_id: 0.0}
    prev: dict[int, int | None] = {start_id: None}
    heap: list[tuple[float, int]] = [(0.0, start_id)]
    visited: set[int] = set()

    while heap:
        d, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        if node == end_id:
            break
        for nxt, w, _ in adj.get(node, ()):
            nd = d + w
            if nxt not in dist or nd < dist[nxt]:
                dist[nxt] = nd
                prev[nxt] = node
                heapq.heappush(heap, (nd, nxt))

    if end_id not in dist:
        return None, 0.0, "dijkstra_igp_cost"

    path: list[int] = []
    cur: int | None = end_id
    while cur is not None:
        path.append(cur)
        cur = prev.get(cur)
    path.reverse()
    return path, dist[end_id], "dijkstra_igp_cost"


def path_segments(
    db: Session,
    device_ids: list[int],
    *,
    cost_cache: dict[int, dict[str, int]] | None = None,
) -> list[dict]:
    """Per-hop link segments with IGP cost metadata."""
    if len(device_ids) < 2:
        return []
    if cost_cache is None:
        cost_cache = igp_cost_service.build_cost_cache(db, set(device_ids))

    segments: list[dict] = []
    for i in range(len(device_ids) - 1):
        a_id, b_id = device_ids[i], device_ids[i + 1]
        link = _find_link(db, a_id, b_id)
        if not link:
            segments.append({
                "sequence": i,
                "from_device_id": a_id,
                "to_device_id": b_id,
                "link_id": None,
                "interface": None,
                "igp_cost": None,
                "cost_learned": False,
                "connected": False,
            })
            continue
        cost, iface, learned = igp_cost_service.link_transit_cost(
            db, link, a_id, cost_cache=cost_cache
        )
        egress_iface = link.interface_a if a_id == link.device_a_id else link.interface_z
        bb = igp_cost_service.lookup_backbone_interface(
            igp_cost_service.device_backbone_interfaces(db, a_id),
            egress_iface,
        )
        segments.append({
            "sequence": i,
            "from_device_id": a_id,
            "to_device_id": b_id,
            "link_id": link.id,
            "link_name": link.name,
            "interface": iface,
            "igp_cost": cost if learned else None,
            "cost_learned": learned,
            "backbone": bool(bb),
            "igp_process": bb.get("igp_process") if bb else None,
            "connected": True,
        })
    return segments


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
    *,
    use_igp_weights: bool = True,
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
    if use_igp_weights:
        weighted, _, _ = shortest_path_weighted(db, a_id, z_id)
        if weighted:
            return [d for i in weighted if (d := _device_row(db, i))]
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
            "igp_algorithm": None,
            "total_igp_cost": None,
            "segments": [],
        }

    if path_mode == PathMode.EXPLICIT_SR:
        chain = build_device_chain(
            db, endpoint_ids, via_ids, PathMode.EXPLICIT_SR, use_igp_weights=False
        )
        if len(chain) <= 1:
            hop_types = ["endpoint"] * len(chain)
        elif len(chain) == 2:
            hop_types = ["endpoint", "endpoint"]
        else:
            hop_types = ["endpoint"] + ["via"] * (len(chain) - 2) + ["endpoint"]
        igp_algorithm = "explicit_sr"
        total_igp_cost = None
    else:
        a_id, z_id = endpoint_ids[0], endpoint_ids[-1]
        chain_ids, total_igp_cost, igp_algorithm = shortest_path_weighted(db, a_id, z_id)
        if not chain_ids:
            chain_ids = shortest_path(db, a_id, z_id) or [a_id, z_id]
            igp_algorithm = "bfs_hop_count"
            total_igp_cost = float(max(len(chain_ids) - 1, 0))
        chain = [d for i in chain_ids if (d := _device_row(db, i))]
        hop_types = ["auto"] * len(chain)
        if any(d.overlay_tech == OverlayTech.VXLAN_EVPN for d in chain):
            reason = reason or VXLAN_LIMITATION
        elif all(d.overlay_tech == OverlayTech.SRMPLS_EVPN for d in chain):
            reason = "SR-MPLS 未指定经由设备时将按 IS-IS SR 最短路径转发（auto）"

    chain_ids = [d.id for d in chain]
    cost_cache = igp_cost_service.build_cost_cache(db, set(chain_ids))
    segments = path_segments(db, chain_ids, cost_cache=cost_cache)

    hops = [
        _hop_from_device(d, hop_types[i] if i < len(hop_types) else "auto").as_dict()
        for i, d in enumerate(chain)
    ]
    conn_errors = validate_connectivity(db, chain_ids)
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
        "igp_algorithm": igp_algorithm,
        "total_igp_cost": total_igp_cost,
        "segments": segments,
    }


def full_path_for_circuit(db: Session, circuit: Circuit) -> list[Device]:
    endpoint_ids = [ep.device_id for ep in sorted(
        circuit.endpoints, key=lambda e: (e.label != "A", e.label, e.id)
    )]
    via_ids = [h.device_id for h in sorted(circuit.path_hops, key=lambda h: h.sequence)]
    use_weights = circuit.path_mode != PathMode.EXPLICIT_SR
    return build_device_chain(
        db, endpoint_ids, via_ids, circuit.path_mode, use_igp_weights=use_weights
    )


def save_path_hops(db: Session, circuit: Circuit, via_device_ids: list[int]) -> None:
    for hop in list(circuit.path_hops):
        db.delete(hop)
    db.flush()
    for seq, device_id in enumerate(via_device_ids):
        db.add(CircuitPathHop(circuit_id=circuit.id, device_id=device_id, sequence=seq))
    db.flush()
