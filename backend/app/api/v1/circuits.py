"""Circuit (专线) management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
import difflib

from app.models.circuit import Circuit, CircuitEndpoint
from app.models.config_job import ConfigJob
from app.models.device import Device
from app.models.offering import ServiceOffering
from app.models.tenant import Tenant
from app.models.user import User
from app.models.workorder import WorkOrder
from app.schemas.circuit import (
    CircuitCreate,
    CircuitEndpointCreate,
    CircuitEndpointOut,
    CircuitOut,
    CircuitUpdate,
)
from app.services import allocation, probe, validation

router = APIRouter()


def _site_asn_for_endpoints(db: Session, endpoints: list[CircuitEndpoint]) -> int | None:
    for ep in endpoints:
        device = db.get(Device, ep.device_id)
        if device and device.bgp_asn:
            return device.bgp_asn
        if device and device.site and device.site.bgp_asn:
            return device.site.bgp_asn
    return None


@router.get("", response_model=list[CircuitOut])
def list_circuits(
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Circuit).order_by(Circuit.id)
    if tenant_id:
        stmt = stmt.where(Circuit.tenant_id == tenant_id)
    return db.execute(stmt).scalars().all()


@router.post("", response_model=CircuitOut, status_code=201)
def create_circuit(
    payload: CircuitCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    if not db.get(Tenant, payload.tenant_id):
        raise HTTPException(status_code=404, detail="tenant not found")

    data = payload.model_dump(exclude={"endpoints", "code", "offering_id"})

    # Apply offering defaults (only where the request left fields at default).
    if payload.offering_id:
        offering = db.get(ServiceOffering, payload.offering_id)
        if not offering:
            raise HTTPException(status_code=404, detail="offering not found")
        data["service_type"] = offering.service_type
        data["bandwidth_mbps"] = offering.bandwidth_mbps
        data["mtu"] = offering.mtu
        if offering.sla_target:
            data["sla_target"] = offering.sla_target
        if offering.cos:
            data["cos"] = offering.cos

    circuit = Circuit(**data)
    circuit.code = payload.code or allocation.next_circuit_code(db)
    db.add(circuit)
    db.flush()

    endpoints: list[CircuitEndpoint] = []
    for ep in payload.endpoints:
        if not db.get(Device, ep.device_id):
            raise HTTPException(
                status_code=404, detail=f"device {ep.device_id} not found"
            )
        endpoint = CircuitEndpoint(circuit_id=circuit.id, **ep.model_dump())
        db.add(endpoint)
        endpoints.append(endpoint)
    db.flush()

    asn = _site_asn_for_endpoints(db, endpoints)
    allocation.auto_allocate_circuit_fields(db, circuit, asn)

    db.commit()
    db.refresh(circuit)
    return circuit


@router.get("/{circuit_id}", response_model=CircuitOut)
def get_circuit(
    circuit_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    return circuit


@router.get("/{circuit_id}/validate")
def validate_circuit(
    circuit_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Run pre-flight compliance checks on a circuit."""
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    return validation.summarize(validation.validate_circuit(db, circuit))


def _circuit_jobs(db: Session, circuit_id: int) -> list[tuple[ConfigJob, str]]:
    rows = db.execute(
        select(ConfigJob, WorkOrder.code)
        .join(WorkOrder, WorkOrder.id == ConfigJob.work_order_id)
        .where(WorkOrder.circuit_id == circuit_id)
        .order_by(ConfigJob.id)
    ).all()
    return [(row[0], row[1]) for row in rows]


@router.post("/{circuit_id}/probe")
def probe_circuit(
    circuit_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Run an on-demand end-to-end path probe (records a telemetry sample)."""
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    result = probe.probe_circuit(db, circuit)
    db.commit()
    return result


@router.get("/{circuit_id}/config-history")
def config_history(
    circuit_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Per-device timeline of rendered configuration versions."""
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    device_names = {d.id: d.name for d in db.execute(select(Device)).scalars().all()}
    history: dict[int, dict] = {}
    for job, wo_code in _circuit_jobs(db, circuit_id):
        entry = history.setdefault(
            job.device_id,
            {"device_id": job.device_id,
             "device": device_names.get(job.device_id, job.device_id),
             "versions": []},
        )
        entry["versions"].append({
            "job_id": job.id,
            "work_order": wo_code,
            "operation": job.operation,
            "status": job.status.value,
            "transport": job.transport,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "rendered_config": job.rendered_config,
        })
    return {"circuit": circuit.code, "devices": list(history.values())}


@router.get("/{circuit_id}/config-diff")
def config_diff(
    circuit_id: int,
    device_id: int,
    a: int | None = None,
    b: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Unified diff between two config versions of a device on this circuit.

    Defaults to the two most recent versions when a/b are not given.
    """
    if not db.get(Circuit, circuit_id):
        raise HTTPException(status_code=404, detail="circuit not found")
    jobs = [j for j, _wo in _circuit_jobs(db, circuit_id) if j.device_id == device_id]
    if len(jobs) < 1:
        raise HTTPException(status_code=404, detail="no config versions for device")

    def _by_id(jid: int) -> ConfigJob | None:
        return next((j for j in jobs if j.id == jid), None)

    if a and b:
        job_a, job_b = _by_id(a), _by_id(b)
    elif len(jobs) >= 2:
        job_a, job_b = jobs[-2], jobs[-1]
    else:
        job_a, job_b = None, jobs[-1]
    if not job_b:
        raise HTTPException(status_code=404, detail="version not found")

    left = (job_a.rendered_config or "") if job_a else ""
    right = job_b.rendered_config or ""
    diff = "\n".join(
        difflib.unified_diff(
            left.splitlines(), right.splitlines(),
            fromfile=f"job-{job_a.id}" if job_a else "empty",
            tofile=f"job-{job_b.id}",
            lineterm="",
        )
    )
    return {
        "device_id": device_id,
        "from_job": job_a.id if job_a else None,
        "to_job": job_b.id,
        "changed": left != right,
        "diff": diff or "(无差异 / no changes)",
    }


@router.patch("/{circuit_id}", response_model=CircuitOut)
def update_circuit(
    circuit_id: int,
    payload: CircuitUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(circuit, k, v)
    db.commit()
    db.refresh(circuit)
    return circuit


@router.delete("/{circuit_id}", status_code=204)
def delete_circuit(
    circuit_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    db.delete(circuit)
    db.commit()


@router.post(
    "/{circuit_id}/endpoints", response_model=CircuitEndpointOut, status_code=201
)
def add_endpoint(
    circuit_id: int,
    payload: CircuitEndpointCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    if not db.get(Device, payload.device_id):
        raise HTTPException(status_code=404, detail="device not found")
    endpoint = CircuitEndpoint(circuit_id=circuit_id, **payload.model_dump())
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return endpoint


@router.delete("/{circuit_id}/endpoints/{endpoint_id}", status_code=204)
def delete_endpoint(
    circuit_id: int,
    endpoint_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    endpoint = db.get(CircuitEndpoint, endpoint_id)
    if not endpoint or endpoint.circuit_id != circuit_id:
        raise HTTPException(status_code=404, detail="endpoint not found")
    db.delete(endpoint)
    db.commit()
