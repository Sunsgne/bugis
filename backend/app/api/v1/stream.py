"""Server-Sent Events (SSE) stream for live dashboard & alarm updates.

EventSource cannot set Authorization headers, so this endpoint accepts the
JWT via a `token` query parameter and pushes periodic JSON snapshots.
"""
from __future__ import annotations

import json
import time
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from starlette.responses import StreamingResponse

from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.alarm import Alarm
from app.models.circuit import Circuit
from app.models.device import Device
from app.models.enums import AlarmStatus, CircuitStatus
from app.models.tenant import Tenant
from app.models.user import User

router = APIRouter()


def _snapshot() -> dict:
    db = SessionLocal()
    try:
        active_alarms = db.scalar(
            select(func.count(Alarm.id)).where(Alarm.status != AlarmStatus.CLEARED)
        ) or 0
        return {
            "ts": time.time(),
            "tenants": db.scalar(select(func.count(Tenant.id))) or 0,
            "devices": db.scalar(select(func.count(Device.id))) or 0,
            "circuits": db.scalar(select(func.count(Circuit.id))) or 0,
            "circuits_active": db.scalar(
                select(func.count(Circuit.id)).where(
                    Circuit.status == CircuitStatus.ACTIVE
                )
            ) or 0,
            "active_alarms": active_alarms,
        }
    finally:
        db.close()


@router.get("/events")
def stream_events(
    token: str = Query(...),
    interval: int = Query(5, ge=2, le=60),
):
    username = decode_access_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="invalid token")
    db = SessionLocal()
    try:
        user = db.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="invalid user")
    finally:
        db.close()

    def event_gen() -> Iterator[str]:
        # Stream for a bounded duration; the client (EventSource) auto-reconnects.
        max_iterations = max(1, int(600 / interval))
        for _ in range(max_iterations):
            payload = json.dumps(_snapshot())
            yield f"event: snapshot\ndata: {payload}\n\n"
            time.sleep(interval)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
