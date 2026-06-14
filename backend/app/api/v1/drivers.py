"""Driver catalog & ad-hoc config rendering endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.drivers import list_drivers
from app.models.enums import (
    OverlayTech,
    ServiceType,
    Vendor,
    WorkOrderType,
)
from app.models.user import User

router = APIRouter()


@router.get("")
def drivers_catalog(_: User = Depends(get_current_user)):
    return {
        "drivers": list_drivers(),
        "vendors": [v.value for v in Vendor],
        "overlay_tech": [o.value for o in OverlayTech],
        "service_types": [s.value for s in ServiceType],
        "work_order_types": [w.value for w in WorkOrderType],
    }
