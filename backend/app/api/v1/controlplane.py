"""Bugis SDN controller control-plane API (VTEPs, EVPN RIB, topology)."""
from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.controller import controller as bugis
from app.core.database import get_db
from app.models.controlplane import EvpnRoute, VtepPeer
from app.models.user import User

router = APIRouter()


@router.get("/status")
def controller_status(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return bugis.status(db)


@router.get("/vteps")
def list_vteps(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    peers = db.execute(select(VtepPeer).order_by(VtepPeer.id)).scalars().all()
    return [
        {
            "id": p.id,
            "device_id": p.device_id,
            "name": p.name,
            "vtep_ip": p.vtep_ip,
            "asn": p.asn,
            "status": p.status.value,
            "vnis": [int(v) for v in p.vnis.split(",") if v],
            "last_seen": p.last_seen.isoformat() if p.last_seen else None,
        }
        for p in peers
    ]


@router.get("/routes")
def list_routes(
    vni: int | None = None,
    route_type: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(EvpnRoute).order_by(EvpnRoute.vni, EvpnRoute.id)
    if vni is not None:
        stmt = stmt.where(EvpnRoute.vni == vni)
    routes = db.execute(stmt).scalars().all()
    if route_type:
        routes = [r for r in routes if r.route_type.value == route_type]
    return [
        {
            "id": r.id,
            "type": r.route_type.value,
            "vni": r.vni,
            "rd": r.rd,
            "rt": r.rt,
            "mac": r.mac,
            "ip": r.ip_addr,
            "vtep_ip": r.vtep_ip,
            "next_hop": r.next_hop,
            "circuit_id": r.circuit_id,
        }
        for r in routes
    ]


@router.get("/topology")
def overlay_topology(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Overlay topology: VTEP nodes and full-mesh edges per VNI."""
    peers = db.execute(select(VtepPeer)).scalars().all()
    nodes = [
        {"id": p.device_id, "name": p.name, "vtep_ip": p.vtep_ip,
         "vnis": [int(v) for v in p.vnis.split(",") if v], "status": p.status.value}
        for p in peers
    ]
    # Build per-VNI VTEP membership to render the overlay full mesh.
    vni_members: dict[int, list[int]] = defaultdict(list)
    for p in peers:
        for v in p.vnis.split(","):
            if v:
                vni_members[int(v)].append(p.device_id)
    edges = []
    for vni, members in vni_members.items():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                edges.append({"vni": vni, "source": members[i], "target": members[j]})
    return {"nodes": nodes, "edges": edges, "vnis": sorted(vni_members.keys())}
