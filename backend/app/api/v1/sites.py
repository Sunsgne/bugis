"""Site / DC CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
from app.models.device import Device
from app.models.site import Site
from app.models.user import User
from app.schemas.site import SiteCreate, SiteOut, SiteUpdate

router = APIRouter()


@router.get("", response_model=list[SiteOut])
def list_sites(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.execute(select(Site).order_by(Site.id)).scalars().all()


@router.post("", response_model=SiteOut, status_code=201)
def create_site(
    payload: SiteCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    if db.execute(select(Site).where(Site.code == payload.code)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="site code already exists")
    site = Site(**payload.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.get("/{site_id}", response_model=SiteOut)
def get_site(
    site_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    site = db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="site not found")
    return site


@router.patch("/{site_id}", response_model=SiteOut)
def update_site(
    site_id: int,
    payload: SiteUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    site = db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="site not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(site, k, v)
    db.commit()
    db.refresh(site)
    return site


@router.delete("/{site_id}", status_code=204)
def delete_site(
    site_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    site = db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="site not found")
    device_count = db.scalar(
        select(func.count(Device.id)).where(Device.site_id == site_id)
    ) or 0
    if device_count:
        raise HTTPException(
            status_code=409,
            detail=f"站点下仍有 {device_count} 台设备，请先迁移或删除设备后再删除站点",
        )
    db.delete(site)
    db.commit()
