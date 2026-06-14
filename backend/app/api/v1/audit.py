"""Audit log endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.common import TimestampedSchema

router = APIRouter()


class AuditOut(TimestampedSchema):
    id: int
    actor: str
    method: str
    path: str
    status_code: int
    source_ip: str | None = None
    summary: str | None = None


@router.get("", response_model=list[AuditOut])
def list_audit(
    actor: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if actor:
        stmt = stmt.where(AuditLog.actor == actor)
    return db.execute(stmt).scalars().all()
