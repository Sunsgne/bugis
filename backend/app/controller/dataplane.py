"""Controller-coordinated data-plane programming tracking."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.controlplane import DataPlaneBinding
from app.models.device import Device
from app.models.enums import DataPlaneState
from app.models.circuit import Circuit, CircuitEndpoint


def plan_bindings(
    db: Session,
    circuit: Circuit,
    endpoints: list[CircuitEndpoint],
    operation: str,
    work_order_id: int | None = None,
) -> list[DataPlaneBinding]:
    bindings: list[DataPlaneBinding] = []
    for ep in endpoints:
        if not ep.device:
            continue
        existing = db.execute(
            select(DataPlaneBinding).where(
                DataPlaneBinding.circuit_id == circuit.id,
                DataPlaneBinding.device_id == ep.device_id,
                DataPlaneBinding.operation == operation,
            )
        ).scalar_one_or_none()
        binding = existing or DataPlaneBinding(
            circuit_id=circuit.id,
            device_id=ep.device_id,
            operation=operation,
            transport=_transport_for(ep.device),
            work_order_id=work_order_id,
            state=DataPlaneState.PENDING,
        )
        if existing is None:
            db.add(binding)
        else:
            binding.work_order_id = work_order_id
            binding.state = DataPlaneState.PENDING
        bindings.append(binding)
    db.flush()
    return bindings


def _transport_for(device: Device) -> str:
    from app.services import device_management

    try:
        return device_management.effective_transport(device)
    except Exception:
        return "netconf"


def mark_rendered(
    db: Session, circuit_id: int, device_id: int, operation: str, config: str
) -> None:
    binding = db.execute(
        select(DataPlaneBinding).where(
            DataPlaneBinding.circuit_id == circuit_id,
            DataPlaneBinding.device_id == device_id,
            DataPlaneBinding.operation == operation,
        ).order_by(DataPlaneBinding.id.desc()).limit(1)
    ).scalar_one_or_none()
    if not binding:
        return
    binding.state = DataPlaneState.RENDERED
    binding.config_preview = config[:8000] if config else None
    db.flush()


def mark_applied(
    db: Session,
    circuit_id: int,
    device_id: int,
    operation: str,
    output: str = "",
    success: bool = True,
) -> None:
    binding = db.execute(
        select(DataPlaneBinding).where(
            DataPlaneBinding.circuit_id == circuit_id,
            DataPlaneBinding.device_id == device_id,
            DataPlaneBinding.operation == operation,
        ).order_by(DataPlaneBinding.id.desc()).limit(1)
    ).scalar_one_or_none()
    if not binding:
        return
    binding.state = DataPlaneState.APPLIED if success else DataPlaneState.FAILED
    binding.output = output[:4000] if output else None
    db.flush()


def list_bindings(db: Session, circuit_id: int | None = None) -> list[dict]:
    stmt = select(DataPlaneBinding).order_by(DataPlaneBinding.id.desc())
    if circuit_id is not None:
        stmt = stmt.where(DataPlaneBinding.circuit_id == circuit_id)
    rows = db.execute(stmt.limit(200)).scalars().all()
    return [
        {
            "id": b.id,
            "circuit_id": b.circuit_id,
            "device_id": b.device_id,
            "work_order_id": b.work_order_id,
            "operation": b.operation,
            "transport": b.transport,
            "state": b.state.value,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in rows
    ]
