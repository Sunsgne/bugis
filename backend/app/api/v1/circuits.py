"""Circuit (专线) management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
from app.models.circuit import Circuit, CircuitEndpoint
from app.models.device import Device
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.circuit import (
    CircuitCreate,
    CircuitEndpointCreate,
    CircuitEndpointOut,
    CircuitOut,
    CircuitUpdate,
)
from app.services import allocation, validation

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

    data = payload.model_dump(exclude={"endpoints", "code"})
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
