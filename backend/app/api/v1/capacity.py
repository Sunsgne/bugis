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
from app.schemas.link import LinkCreate, LinkOut, LinkUpdate
from app.services import capacity_service

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
    link = Link(**payload.model_dump())
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


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
