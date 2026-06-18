"""Work order (工单) endpoints driving the provisioning lifecycle."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.config import settings
from app.core.database import get_db
from app.drivers import get_driver
from app.models.circuit import Circuit
from app.models.device import Device
from app.models.enums import WorkOrderType
from app.models.user import User
from app.models.workorder import WorkOrder
from app.schemas.workorder import (
    ApprovalRequest,
    ProvisionRequest,
    ProvisionResultOut,
    WorkOrderCreate,
    WorkOrderOut,
    WorkOrderUpdate,
)
from app.models.enums import WorkOrderStatus
from app import worker
from app.services import ansible_export, orchestrator

router = APIRouter()


def _enrich_work_order(db: Session, wo: WorkOrder) -> dict:
    device_names = {
        d.id: d.name
        for d in db.execute(
            select(Device).where(
                Device.id.in_({job.device_id for job in wo.config_jobs} or {0})
            )
        ).scalars().all()
    }
    data = WorkOrderOut.model_validate(wo).model_dump()
    for job in data.get("config_jobs") or []:
        job["device_name"] = device_names.get(job["device_id"])
    return data


def _provision_result(db: Session, wo: WorkOrder, circuit: Circuit) -> dict:
    payload = _enrich_work_order(db, wo)
    payload["circuit_status"] = circuit.status.value
    payload["circuit_code"] = circuit.code
    payload["dry_run"] = settings.dry_run
    return payload


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


@router.patch("/{wo_id}", response_model=WorkOrderOut)
def update_work_order(
    wo_id: int,
    payload: WorkOrderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    wo = db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="work order not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(wo, k, v)
    if data:
        orchestrator._log(db, wo, f"工单已编辑 ({', '.join(data)})", actor=user.username)
    db.commit()
    db.refresh(wo)
    return wo


@router.post("/{wo_id}/cancel", response_model=WorkOrderOut)
def cancel_work_order(
    wo_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    wo = db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="work order not found")
    if wo.status in (WorkOrderStatus.RUNNING, WorkOrderStatus.COMPLETED):
        raise HTTPException(status_code=400, detail="cannot cancel a running/completed work order")
    wo.status = WorkOrderStatus.CANCELLED
    orchestrator._log(db, wo, "工单已取消", level="warning", actor=user.username)
    db.commit()
    db.refresh(wo)
    return wo


@router.delete("/{wo_id}", status_code=204)
def delete_work_order(
    wo_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    wo = db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="work order not found")
    if wo.status == WorkOrderStatus.RUNNING:
        raise HTTPException(status_code=400, detail="cannot delete a running work order")
    db.delete(wo)
    db.commit()


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


@router.post("/provision/{circuit_id}", response_model=ProvisionResultOut, status_code=201)
def provision_circuit(
    circuit_id: int,
    wo_type: WorkOrderType = WorkOrderType.PROVISION,
    body: ProvisionRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    """Convenience one-shot: create -> submit -> approve -> execute."""
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    payload: str | None = None
    if body and body.previous_endpoints:
        payload = json.dumps(
            {
                "previous_endpoints": [
                    ep.model_dump(mode="json") for ep in body.previous_endpoints
                ]
            }
        )
    wo = orchestrator.create_work_order(
        db, circuit, wo_type, requested_by=user.username, payload=payload
    )
    orchestrator.submit(db, wo, actor=user.username)
    orchestrator.approve(db, wo, user.username, approve_it=True)
    if getattr(settings, "async_provisioning", False):
        # Queue for the background worker and return immediately so the request
        # thread is never held by the (synchronous) device push. The frontend
        # polls GET /work-orders/{id} for live progress.
        wo.status = WorkOrderStatus.SCHEDULED
        orchestrator._log(
            db, wo, "已加入开通队列，后台异步执行（可在工单详情查看进度）",
            actor=user.username,
        )
        db.commit()
        db.refresh(wo)
        worker.enqueue(wo.id)
        return _provision_result(db, wo, circuit)
    orchestrator.execute(db, wo, actor=user.username)
    db.commit()
    db.refresh(wo)
    return _provision_result(db, wo, circuit)


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


@router.get("/{wo_id}/ansible")
def export_ansible(
    wo_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    """Export this work order's config as Ansible inventory + playbook."""
    wo = db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="work order not found")
    try:
        return ansible_export.export_work_order(db, wo)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="该工单没有可导出的配置（需已完成执行且含 rendered config）",
        ) from None


@router.get("/{wo_id}/ansible/download")
def download_ansible_archive(
    wo_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    """Download inventory + playbook + per-device configs as a zip archive."""
    wo = db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="work order not found")
    try:
        payload, filename = ansible_export.export_work_order_zip(db, wo)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="该工单没有可导出的配置（需已完成执行且含 rendered config）",
        ) from None
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
