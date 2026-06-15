"""Platform settings API (branding customization)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
from app.models.user import User
from app.schemas.platform_settings import BrandingOut, BrandingUpdate, PlatformSettingsOut
from app.services import platform_settings as svc

router = APIRouter()


@router.get("/platform", response_model=PlatformSettingsOut)
def get_platform_settings(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return svc.to_out(svc.get_or_create(db))


@router.patch("/platform", response_model=PlatformSettingsOut)
def update_platform_settings(
    payload: BrandingUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    row = svc.update_branding(db, payload)
    return svc.to_out(row)
