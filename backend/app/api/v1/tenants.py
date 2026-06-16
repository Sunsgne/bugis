"""Tenant CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator, require_platform_user
from app.core.database import get_db
from app.models.circuit import Circuit
from app.models.enums import CircuitStatus
from app.models.tenant import Tenant
from app.core.security import hash_password
from app.models.enums import UserRole, UserScope
from app.models.user import User
from app.schemas.auth import TenantUserCreate, UserOut
from app.schemas.pagination import PaginatedResponse, paginate_query, paginated
from app.schemas.tenant import (
    TenantCreate,
    TenantListOut,
    TenantOut,
    TenantOverview,
    TenantSummary,
    TenantUpdate,
)

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


def _tenant_list_stmt(q: str | None = None):
    circuits_total = func.count(Circuit.id).label("circuits_total")
    stmt = (
        select(Tenant, circuits_total)
        .outerjoin(Circuit, Circuit.tenant_id == Tenant.id)
        .group_by(Tenant.id)
        .order_by(Tenant.name)
    )
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Tenant.name.ilike(like), Tenant.code.ilike(like)))
    return stmt


def _to_tenant_list_out(row: tuple[Tenant, int]) -> TenantListOut:
    tenant, circuits_total = row[0], row[1]
    base = TenantListOut.model_validate(tenant, from_attributes=True)
    return base.model_copy(update={"circuits_total": int(circuits_total or 0)})


@router.get("/overview", response_model=TenantOverview)
def tenant_overview(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    tenants_total = int(db.scalar(select(func.count()).select_from(Tenant)) or 0)
    circuits = db.execute(select(Circuit)).scalars().all()
    active = decommissioned = draft = 0
    active_bw = 0
    for c in circuits:
        if c.status == CircuitStatus.ACTIVE:
            active += 1
            active_bw += c.bandwidth_mbps
        elif c.status == CircuitStatus.DECOMMISSIONED:
            decommissioned += 1
        elif c.status == CircuitStatus.DRAFT:
            draft += 1
    return TenantOverview(
        tenants_total=tenants_total,
        circuits_total=len(circuits),
        circuits_active=active,
        circuits_decommissioned=decommissioned,
        circuits_draft=draft,
        active_bandwidth_mbps=active_bw,
    )


@router.get("", response_model=PaginatedResponse[TenantListOut])
def list_tenants(
    q: str | None = Query(None, description="Search name or code"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = _tenant_list_stmt(q)
    rows, total = paginate_query(db, stmt, page=page, page_size=page_size)
    return paginated(
        [_to_tenant_list_out(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/summaries", response_model=list[TenantSummary])
def list_tenant_summaries(
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if tenant_id is not None:
        if not db.get(Tenant, tenant_id):
            raise HTTPException(status_code=404, detail="tenant not found")
        return [_build_tenant_summary(db, tenant_id)]
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


@router.get("/{tenant_id}/users", response_model=list[UserOut])
def list_tenant_users(
    tenant_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_user),
):
    if not db.get(Tenant, tenant_id):
        raise HTTPException(status_code=404, detail="tenant not found")
    return db.execute(
        select(User)
        .where(User.tenant_id == tenant_id, User.scope == UserScope.TENANT)
        .order_by(User.username)
    ).scalars().all()


@router.post("/{tenant_id}/users", response_model=UserOut, status_code=201)
def create_tenant_user(
    tenant_id: int,
    payload: TenantUserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant not found")
    exists = db.execute(
        select(User).where(User.username == payload.username)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="username already exists")
    user = User(
        username=payload.username,
        full_name=payload.full_name or tenant.name,
        email=payload.email or tenant.contact_email,
        role=payload.role,
        scope=UserScope.TENANT,
        tenant_id=tenant_id,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{tenant_id}/users/{user_id}", status_code=204)
def delete_tenant_user(
    tenant_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    user = db.get(User, user_id)
    if not user or user.tenant_id != tenant_id or user.scope != UserScope.TENANT:
        raise HTTPException(status_code=404, detail="portal user not found")
    db.delete(user)
    db.commit()
