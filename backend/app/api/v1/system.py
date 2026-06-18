"""System / scheduler status endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import __version__, scheduler, worker
from app.api.deps import get_current_user, require_operator, require_platform_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.platform_settings import BrandingOut
from app.services import platform_settings as platform_cfg, snmp_settings as snmp_cfg

router = APIRouter()


@router.get("/info")
def system_info(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    snmp = snmp_cfg.get_or_create(db)
    return {
        "version": __version__,
        "app_env": settings.app_env,
        "dry_run": settings.dry_run,
        "telemetry_simulation": settings.telemetry_simulation,
        "snmp_enabled": snmp.enabled,
        "production_data_mode": not settings.dry_run and not settings.telemetry_simulation,
        "scheduler": scheduler.status(),
    }


@router.get("/branding", response_model=BrandingOut)
def public_branding(db: Session = Depends(get_db)):
    """Public branding for login page (no auth required)."""
    return platform_cfg.to_branding(platform_cfg.get_or_create(db))


@router.get("/snmp-defaults")
def snmp_defaults(db: Session = Depends(get_db)):
    """Platform default SNMP parameters for device onboarding forms."""
    from app.services import snmp_device as snmp_cfg

    return snmp_cfg.snmp_defaults(db)


@router.get("/management-defaults")
def southbound_defaults(_: User = Depends(require_platform_user), db: Session = Depends(get_db)):
    """Platform default NETCONF/SSH/SNMP parameters for device onboarding."""
    from app.services import device_management

    return device_management.management_defaults(db)


@router.get("/scheduler")
def scheduler_status(_: User = Depends(require_platform_user)):
    return scheduler.status()


@router.post("/scheduler/tick")
def scheduler_tick(_: User = Depends(require_operator)):
    """Force one scheduler tick (telemetry + alarm evaluation)."""
    count = scheduler.run_once()
    return {"generated": count, "status": scheduler.status()}


@router.get("/worker")
def worker_status(_: User = Depends(require_platform_user)):
    """Background provisioning worker status (queue depth, in-flight, totals)."""
    return worker.status()


@router.post("/worker/drain")
def worker_drain(_: User = Depends(require_operator)):
    """Synchronously execute any queued (scheduled) work orders now."""
    processed = worker.process_pending()
    return {"processed": processed, "status": worker.status()}
