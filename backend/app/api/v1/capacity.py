"""Capacity, links and topology endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
from app.models.device import Device
from app.models.link import Link
from app.models.user import User
from app.schemas.link import (
    InterfaceCandidateOut,
    LinkBulkCreate,
    LinkCreate,
    LinkOut,
    LinkPlanOut,
    LinkUpdate,
)
from app.services import capacity_service, link_planner

router = APIRouter()


# --- links -----------------------------------------------------------------
@router.get("/links", response_model=list[LinkOut])
def list_links(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.execute(select(Link).order_by(Link.id)).scalars().all()


@router.post("/links", response_model=LinkOut, status_code=201)
def create_link(
    payload: LinkCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    for did in (payload.device_a_id, payload.device_z_id):
        if not db.get(Device, did):
            raise HTTPException(status_code=404, detail=f"device {did} not found")
    try:
        data = link_planner.resolve_link_payload(db, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    link = Link(**data)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.post("/links/bulk", response_model=list[LinkOut], status_code=201)
def create_links_bulk(
    payload: LinkBulkCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    created: list[Link] = []
    for item in payload.links:
        for did in (item.device_a_id, item.device_z_id):
            if not db.get(Device, did):
                raise HTTPException(status_code=404, detail=f"device {did} not found")
        try:
            data = link_planner.resolve_link_payload(db, item.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        link = Link(**data)
        db.add(link)
        created.append(link)
    db.commit()
    for link in created:
        db.refresh(link)
    return created


@router.get("/links/suggestions", response_model=list[LinkPlanOut])
def list_link_suggestions(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    return link_planner.suggest_backbone_links(db)


@router.get("/links/plan", response_model=LinkPlanOut)
def plan_link_between_devices(
    device_a_id: int,
    device_z_id: int,
    interface_a: str | None = None,
    interface_z: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    device_a = db.get(Device, device_a_id)
    device_z = db.get(Device, device_z_id)
    if not device_a or not device_z:
        raise HTTPException(status_code=404, detail="device not found")
    plan = link_planner.plan_link(
        db, device_a, device_z, interface_a=interface_a, interface_z=interface_z
    )
    if not plan:
        raise HTTPException(status_code=400, detail="未找到可用上联端口，请先执行 SNMP 发现")
    return plan


@router.get("/devices/{device_id}/uplink-candidates", response_model=list[InterfaceCandidateOut])
def list_uplink_candidates(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not db.get(Device, device_id):
        raise HTTPException(status_code=404, detail="device not found")
    return [
        {
            "name": row.name,
            "speed_mbps": row.speed_mbps,
            "oper_status": row.oper_status,
            "score": row.score,
            "reason": row.reason,
        }
        for row in link_planner.rank_interfaces(db, device_id)
    ]


@router.patch("/links/{link_id}", response_model=LinkOut)
def update_link(
    link_id: int,
    payload: LinkUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    link = db.get(Link, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="link not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(link, k, v)
    db.commit()
    db.refresh(link)
    return link


@router.delete("/links/{link_id}", status_code=204)
def delete_link(
    link_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    link = db.get(Link, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="link not found")
    db.delete(link)
    db.commit()


# --- capacity views --------------------------------------------------------
@router.get("/devices")
def device_capacity(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return capacity_service.device_capacity(db)


@router.get("/sites")
def site_capacity(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return capacity_service.site_capacity(db)


@router.get("/links/usage")
def link_usage(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return capacity_service.link_capacity(db)


@router.get("/topology")
def topology(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return capacity_service.topology(db)


@router.post("/links/sync-bandwidth")
def sync_link_bandwidth(
    db: Session = Depends(get_db), _: User = Depends(require_operator)
):
    """Re-read bw(...) tags from port descriptions and refresh link capacity."""
    from app.services import link_monitor

    return link_monitor.sync_all_link_capacity(db)
