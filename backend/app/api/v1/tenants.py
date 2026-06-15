"""Tenant CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
from app.models.circuit import Circuit
from app.models.enums import CircuitStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tenant import TenantCreate, TenantOut, TenantSummary, TenantUpdate

router = APIRouter()


def _build_tenant_summary(db: Session, tenant_id: int) -> TenantSummary:
    circuits = db.execute(
        select(Circuit).where(Circuit.tenant_id == tenant_id)
    ).scalars().all()
    by_type: dict[str, int] = {}
    active_bw = 0
    total_bw = 0
    active = decommissioned = draft = 0
    for c in circuits:
        by_type[c.service_type.value] = by_type.get(c.service_type.value, 0) + 1
        total_bw += c.bandwidth_mbps
        if c.status == CircuitStatus.ACTIVE:
            active += 1
            active_bw += c.bandwidth_mbps
        elif c.status == CircuitStatus.DECOMMISSIONED:
            decommissioned += 1
        elif c.status == CircuitStatus.DRAFT:
            draft += 1
    return TenantSummary(
        tenant_id=tenant_id,
        circuits_total=len(circuits),
        circuits_active=active,
        circuits_decommissioned=decommissioned,
        circuits_draft=draft,
        total_bandwidth_mbps=total_bw,
        active_bandwidth_mbps=active_bw,
        by_service_type=by_type,
    )


@router.get("", response_model=list[TenantOut])
def list_tenants(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.execute(select(Tenant).order_by(Tenant.id)).scalars().all()


@router.get("/summaries", response_model=list[TenantSummary])
def list_tenant_summaries(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    tenants = db.execute(select(Tenant).order_by(Tenant.id)).scalars().all()
    return [_build_tenant_summary(db, t.id) for t in tenants]


@router.get("/{tenant_id}/summary", response_model=TenantSummary)
def get_tenant_summary(
    tenant_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    if not db.get(Tenant, tenant_id):
        raise HTTPException(status_code=404, detail="tenant not found")
    return _build_tenant_summary(db, tenant_id)


@router.post("", response_model=TenantOut, status_code=201)
def create_tenant(
    payload: TenantCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    if db.execute(
        select(Tenant).where(Tenant.code == payload.code)
    ).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="tenant code already exists")
    tenant = Tenant(**payload.model_dump())
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("/{tenant_id}", response_model=TenantOut)
def get_tenant(
    tenant_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant not found")
    return tenant


@router.patch("/{tenant_id}", response_model=TenantOut)
def update_tenant(
    tenant_id: int,
    payload: TenantUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(tenant, k, v)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.delete("/{tenant_id}", status_code=204)
def delete_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant not found")
    db.delete(tenant)
    db.commit()
