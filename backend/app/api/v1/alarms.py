"""Alarm center endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
from app.models.alarm import Alarm
from app.models.circuit import Circuit
from app.models.enums import AlarmSeverity, AlarmStatus
from app.models.user import User
from app.schemas.alarm import AlarmAck, AlarmOut
from app.services import alarm_service, telemetry_service

router = APIRouter()


@router.get("", response_model=list[AlarmOut])
def list_alarms(
    status: AlarmStatus | None = None,
    severity: AlarmSeverity | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Alarm).order_by(Alarm.id.desc()).limit(limit)
    if status:
        stmt = stmt.where(Alarm.status == status)
    if severity:
        stmt = stmt.where(Alarm.severity == severity)
    return db.execute(stmt).scalars().all()


@router.get("/summary")
def alarm_summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    by_sev: dict[str, int] = {}
    for row in db.execute(
        select(Alarm.severity, func.count(Alarm.id))
        .where(Alarm.status != AlarmStatus.CLEARED)
        .group_by(Alarm.severity)
    ).all():
        by_sev[row[0].value] = row[1]
    active = db.scalar(
        select(func.count(Alarm.id)).where(Alarm.status == AlarmStatus.ACTIVE)
    ) or 0
    return {"active": active, "by_severity": by_sev}


@router.post("/evaluate")
def evaluate(db: Session = Depends(get_db), _: User = Depends(require_operator)):
    """Re-evaluate all circuits and raise/clear alarms accordingly."""
    circuits = db.execute(select(Circuit)).scalars().all()
    for c in circuits:
        health = telemetry_service.compute_health(db, c)
        alarm_service.evaluate_circuit_health(db, c, health)
    db.commit()
    active = db.scalar(
        select(func.count(Alarm.id)).where(Alarm.status == AlarmStatus.ACTIVE)
    ) or 0
    return {"evaluated": len(circuits), "active_alarms": active}


@router.post("/{alarm_id}/ack", response_model=AlarmOut)
def ack_alarm(
    alarm_id: int,
    payload: AlarmAck,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    alarm = db.get(Alarm, alarm_id)
    if not alarm:
        raise HTTPException(status_code=404, detail="alarm not found")
    alarm_service.acknowledge(db, alarm, payload.acknowledged_by or user.username)
    db.commit()
    db.refresh(alarm)
    return alarm


@router.post("/{alarm_id}/clear", response_model=AlarmOut)
def clear_alarm(
    alarm_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    alarm = db.get(Alarm, alarm_id)
    if not alarm:
        raise HTTPException(status_code=404, detail="alarm not found")
    alarm_service.clear(db, alarm)
    db.commit()
    db.refresh(alarm)
    return alarm
