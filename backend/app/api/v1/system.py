"""System / scheduler status endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app import __version__, scheduler
from app.api.deps import get_current_user, require_operator
from app.core.config import settings
from app.models.user import User

router = APIRouter()


@router.get("/info")
def system_info(_: User = Depends(get_current_user)):
    return {
        "version": __version__,
        "app_env": settings.app_env,
        "dry_run": settings.dry_run,
        "scheduler": scheduler.status(),
    }


@router.get("/scheduler")
def scheduler_status(_: User = Depends(get_current_user)):
    return scheduler.status()


@router.post("/scheduler/tick")
def scheduler_tick(_: User = Depends(require_operator)):
    """Force one scheduler tick (telemetry + alarm evaluation)."""
    count = scheduler.run_once()
    return {"generated": count, "status": scheduler.status()}
