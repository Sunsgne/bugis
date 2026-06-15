"""Platform runtime settings API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import __version__, scheduler
from app.api.deps import get_current_user, require_operator
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.platform_settings import (
    AllSettingsOut,
    PlatformReadonlyInfo,
    PlatformSettingsOut,
    PlatformSettingsUpdate,
)
from app.services import platform_settings as platform_svc
from app.services import snmp_settings as snmp_svc

router = APIRouter()


def _readonly_info() -> PlatformReadonlyInfo:
    db_url = settings.database_url
    if "@" in db_url or "password" in db_url.lower():
        db_url = db_url.split("@")[-1] if "@" in db_url else "(configured)"
    return PlatformReadonlyInfo(
        version=__version__,
        app_env=settings.app_env,
        app_name=settings.app_name,
        database_url=db_url,
        secret_key_set=settings.secret_key != "change-me-in-production-please-use-a-long-random-string",
    )


@router.get("", response_model=AllSettingsOut)
def get_all_settings(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    platform = platform_svc.get_or_create(db)
    snmp_svc.get_or_create(db)
    return AllSettingsOut(
        platform=platform_svc.to_out(platform),
        readonly=_readonly_info(),
    )


@router.get("/platform", response_model=PlatformSettingsOut)
def get_platform_settings(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return platform_svc.to_out(platform_svc.get_or_create(db))


@router.patch("/platform", response_model=PlatformSettingsOut)
def update_platform_settings(
    payload: PlatformSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    row = platform_svc.update_settings(db, payload)
    return platform_svc.to_out(row)


@router.get("/platform/status")
def platform_runtime_status(_: User = Depends(get_current_user)):
    return {
        "dry_run": settings.dry_run,
        "scheduler": scheduler.status(),
        "metrics_enabled": settings.enable_metrics,
    }
