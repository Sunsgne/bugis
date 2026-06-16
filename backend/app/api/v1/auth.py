"""Authentication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, is_tenant_user, require_admin
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.enums import TenantStatus, UserScope
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import PasswordChangeRequest, Token, UserCreate, UserOut

router = APIRouter()


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.execute(
        select(User).where(User.username == form_data.username)
    ).scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    if is_tenant_user(user):
        if user.tenant_id is None:
            raise HTTPException(status_code=403, detail="门户账号未绑定租户")
        tenant = db.get(Tenant, user.tenant_id)
        if not tenant:
            raise HTTPException(status_code=403, detail="租户不存在")
        if tenant.status != TenantStatus.ACTIVE:
            raise HTTPException(status_code=403, detail="租户已暂停或终止")
    token = create_access_token(subject=user.username)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password", status_code=204)
def change_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="新密码至少 8 位")
    user.hashed_password = hash_password(payload.new_password)
    db.add(user)
    db.commit()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    exists = db.execute(
        select(User).where(User.username == payload.username)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="username already exists")
    user = User(
        username=payload.username,
        full_name=payload.full_name,
        email=payload.email,
        role=payload.role,
        scope=UserScope.PLATFORM,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.execute(select(User)).scalars().all()
