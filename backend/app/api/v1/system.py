"""System / scheduler status endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import __version__, scheduler
from app.api.deps import get_current_user, require_operator
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.platform_settings import BrandingOut
from app.services import platform_settings as platform_cfg

router = APIRouter()


@router.get("/info")
def system_info(_: User = Depends(get_current_user)):
    return {
        "version": __version__,
        "app_env": settings.app_env,
        "dry_run": settings.dry_run,
        "scheduler": scheduler.status(),
    }


@router.get("/branding", response_model=BrandingOut)
def public_branding(db: Session = Depends(get_db)):
    """Public branding for login page (no auth required)."""
    return platform_cfg.to_branding(platform_cfg.get_or_create(db))


@router.get("/snmp-defaults")
def snmp_defaults(_: Session = Depends(get_db)):
    """Platform default SNMP parameters for device onboarding forms."""
    from app.services import snmp_device as snmp_cfg

    return snmp_cfg.snmp_defaults()


@router.get("/scheduler")
def scheduler_status(_: User = Depends(get_current_user)):
    return scheduler.status()


@router.post("/scheduler/tick")
def scheduler_tick(_: User = Depends(require_operator)):
    """Force one scheduler tick (telemetry + alarm evaluation)."""
    count = scheduler.run_once()
    return {"generated": count, "status": scheduler.status()}
