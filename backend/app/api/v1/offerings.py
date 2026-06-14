"""Service offering (套餐) CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
from app.models.offering import ServiceOffering
from app.models.user import User
from app.schemas.offering import OfferingCreate, OfferingOut, OfferingUpdate

router = APIRouter()


@router.get("", response_model=list[OfferingOut])
def list_offerings(
    active: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(ServiceOffering).order_by(ServiceOffering.id)
    if active is not None:
        stmt = stmt.where(ServiceOffering.active == active)
    return db.execute(stmt).scalars().all()


@router.post("", response_model=OfferingOut, status_code=201)
def create_offering(
    payload: OfferingCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    if db.execute(
        select(ServiceOffering).where(ServiceOffering.code == payload.code)
    ).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="offering code already exists")
    offering = ServiceOffering(**payload.model_dump())
    db.add(offering)
    db.commit()
    db.refresh(offering)
    return offering


@router.patch("/{offering_id}", response_model=OfferingOut)
def update_offering(
    offering_id: int,
    payload: OfferingUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    offering = db.get(ServiceOffering, offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="offering not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(offering, k, v)
    db.commit()
    db.refresh(offering)
    return offering


@router.delete("/{offering_id}", status_code=204)
def delete_offering(
    offering_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    offering = db.get(ServiceOffering, offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="offering not found")
    db.delete(offering)
    db.commit()
