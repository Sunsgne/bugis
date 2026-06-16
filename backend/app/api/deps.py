"""Common API dependencies (auth, current user)."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.circuit import Circuit
from app.models.enums import TenantStatus, UserRole, UserScope
from app.models.tenant import Tenant
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_v1_prefix}/auth/login", auto_error=False
)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exc
    username = decode_access_token(token)
    if not username:
        raise credentials_exc
    user = db.execute(
        select(User).where(User.username == username)
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exc
    return user


def is_tenant_user(user: User) -> bool:
    return user.scope == UserScope.TENANT or user.tenant_id is not None


def require_platform_user(user: User = Depends(get_current_user)) -> User:
    if is_tenant_user(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="客户门户账号无法访问运营平台，请使用 /portal 登录",
        )
    return user


def require_tenant_user(user: User = Depends(get_current_user)) -> User:
    if not is_tenant_user(user) or user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要客户门户账号",
        )
    tenant = user.tenant
    if tenant is None:
        raise HTTPException(status_code=403, detail="租户不存在或已删除")
    if tenant.status != TenantStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="租户已暂停或终止，无法登录门户")
    return user


def require_operator(user: User = Depends(require_platform_user)) -> User:
    if user.role == UserRole.VIEWER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="operator or admin role required",
        )
    return user


def require_admin(user: User = Depends(require_platform_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="admin role required"
        )
    return user


def get_tenant_circuit(
    db: Session,
    user: User,
    circuit_id: int,
) -> Circuit:
    circuit = db.get(Circuit, circuit_id)
    if not circuit or circuit.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="circuit not found")
    return circuit
