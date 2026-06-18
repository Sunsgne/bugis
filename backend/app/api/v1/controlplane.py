"""Bugis SDN controller control-plane API (VTEPs, EVPN RIB, topology)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.controller import bgp_peering, controller as bugis, dataplane, ha
from app.core.database import get_db
from app.models.controlplane import EvpnRoute, VtepPeer
from app.models.user import User
from app.services import overlay_inventory

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
    encap: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(EvpnRoute).order_by(EvpnRoute.vni, EvpnRoute.id)
    if vni is not None:
        stmt = stmt.where(EvpnRoute.vni == vni)
    routes = db.execute(stmt).scalars().all()
    if route_type:
        routes = [r for r in routes if r.route_type.value == route_type]
    if encap:
        routes = [r for r in routes if r.encap.value == encap]
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
            "encap": r.encap.value,
            "mpls_label": r.mpls_label,
            "sr_sid": r.sr_sid,
        }
        for r in routes
    ]


@router.get("/topology")
def overlay_topology(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return overlay_inventory.build_overlay_topology(db)


@router.get("/bgp/sessions")
def list_bgp_sessions(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return bgp_peering.list_sessions(db)


@router.post("/bgp/sync")
def sync_bgp_sessions(
    db: Session = Depends(get_db), _: User = Depends(require_operator)
):
    count = bgp_peering.sync_sessions(db)
    db.commit()
    return {"synced": count}


@router.get("/cluster")
def cluster_info(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return ha.cluster_status(db)


@router.get("/dataplane/bindings")
def list_dataplane_bindings(
    circuit_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return dataplane.list_bindings(db, circuit_id)


@router.get("/overlay-inventory")
def get_overlay_inventory(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Fleet-wide VNI/VSI inventory from learned configs (read-only)."""
    return overlay_inventory.fleet_overlay_inventory(db)


@router.post("/overlay-inventory/scan")
def scan_overlay_inventory(
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Re-scan overlay identifiers from latest learned configs; no device push.

    Also reconciles the controller overlay topology with the learned network so
    stale VTEP/VNI edges (e.g. from a failed-then-deleted circuit) are removed.
    """
    result = overlay_inventory.scan_fleet_overlay(db)
    db.commit()
    return result
