"""Service offering (套餐) CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
from app.models.enums import ServiceType
from app.models.offering import ServiceOffering
from app.models.user import User
from app.schemas.offering import OfferingCreate, OfferingOut, OfferingUpdate
from app.schemas.pagination import PaginatedResponse, paginated

router = APIRouter()


def _offering_list_stmt(
    *,
    active: bool | None = None,
    q: str | None = None,
    service_type: ServiceType | None = None,
    tier: str | None = None,
):
    stmt = select(ServiceOffering).order_by(ServiceOffering.id.desc())
    if active is not None:
        stmt = stmt.where(ServiceOffering.active == active)
    if service_type is not None:
        stmt = stmt.where(ServiceOffering.service_type == service_type)
    if tier:
        stmt = stmt.where(ServiceOffering.tier == tier.strip())
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(ServiceOffering.name.ilike(like), ServiceOffering.code.ilike(like))
        )
    return stmt


@router.get("", response_model=PaginatedResponse[OfferingOut])
def list_offerings(
    active: bool | None = None,
    q: str | None = Query(None, description="Search name or code"),
    service_type: ServiceType | None = None,
    tier: str | None = Query(None, description="gold / silver / bronze"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = _offering_list_stmt(active=active, q=q, service_type=service_type, tier=tier)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    items = list(
        db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    )
    return paginated(items, total=total, page=page, page_size=page_size)


@router.get("/{offering_id}", response_model=OfferingOut)
def get_offering(
    offering_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    offering = db.get(ServiceOffering, offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="offering not found")
    return offering


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
