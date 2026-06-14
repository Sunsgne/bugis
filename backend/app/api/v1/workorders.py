"""Work order (工单) endpoints driving the provisioning lifecycle."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
from app.drivers import get_driver
from app.models.circuit import Circuit
from app.models.enums import WorkOrderType
from app.models.user import User
from app.models.workorder import WorkOrder
from app.schemas.workorder import (
    ApprovalRequest,
    WorkOrderCreate,
    WorkOrderOut,
)
from app.services import orchestrator

router = APIRouter()


@router.get("", response_model=list[WorkOrderOut])
def list_work_orders(
    circuit_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(WorkOrder).order_by(WorkOrder.id.desc())
    if circuit_id:
        stmt = stmt.where(WorkOrder.circuit_id == circuit_id)
    return db.execute(stmt).scalars().all()


@router.post("", response_model=WorkOrderOut, status_code=201)
def create_work_order(
    payload: WorkOrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    circuit = db.get(Circuit, payload.circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    wo = orchestrator.create_work_order(
        db,
        circuit,
        payload.type,
        title=payload.title,
        requested_by=payload.requested_by or user.username,
        payload=payload.payload,
        notes=payload.notes,
    )
    db.commit()
    db.refresh(wo)
    return wo


@router.get("/{wo_id}", response_model=WorkOrderOut)
def get_work_order(
    wo_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    wo = db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="work order not found")
    return wo


@router.post("/{wo_id}/submit", response_model=WorkOrderOut)
def submit_work_order(
    wo_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    wo = db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="work order not found")
    try:
        orchestrator.submit(db, wo, actor=user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(wo)
    return wo


@router.post("/{wo_id}/approve", response_model=WorkOrderOut)
def approve_work_order(
    wo_id: int,
    payload: ApprovalRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    wo = db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="work order not found")
    try:
        orchestrator.approve(
            db, wo, payload.approved_by or user.username,
            approve_it=payload.approve, notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(wo)
    return wo


@router.post("/{wo_id}/execute", response_model=WorkOrderOut)
def execute_work_order(
    wo_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    wo = db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="work order not found")
    try:
        orchestrator.execute(db, wo, actor=user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(wo)
    return wo


@router.post("/provision/{circuit_id}", response_model=WorkOrderOut, status_code=201)
def provision_circuit(
    circuit_id: int,
    wo_type: WorkOrderType = WorkOrderType.PROVISION,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    """Convenience one-shot: create -> submit -> approve -> execute."""
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    wo = orchestrator.create_work_order(
        db, circuit, wo_type, requested_by=user.username
    )
    orchestrator.submit(db, wo, actor=user.username)
    orchestrator.approve(db, wo, user.username, approve_it=True)
    orchestrator.execute(db, wo, actor=user.username)
    db.commit()
    db.refresh(wo)
    return wo


@router.get("/{wo_id}/preview")
def preview_work_order(
    wo_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    """Render (dry-run) the configuration without applying it."""
    wo = db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="work order not found")
    circuit = wo.circuit
    operation = "remove" if wo.type == WorkOrderType.DECOMMISSION else "apply"
    previews = []
    for ep in circuit.endpoints:
        device = ep.device
        if not device:
            continue
        driver = get_driver(device.vendor)
        context = {"circuit": circuit, "endpoint": ep, "device": device,
                   "site": device.site}
        previews.append(
            {
                "device": device.name,
                "vendor": device.vendor.value,
                "transport": driver.transport,
                "config": driver.render(circuit.service_type.value, operation, context),
            }
        )
    return {"work_order": wo.code, "operation": operation, "previews": previews}
