"""Delete decommissioned / draft / failed circuits and purge heavy dependencies."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.controller import controller as bugis_controller
from app.models.circuit import Circuit
from app.models.enums import CircuitStatus
from app.models.workorder import WorkOrder
from app.services.circuit_cleanup import purge_circuit_dependencies

DELETABLE_STATUSES = frozenset({
    CircuitStatus.DECOMMISSIONED,
    CircuitStatus.DRAFT,
    CircuitStatus.FAILED,
})


def _detach_work_orders(db: Session, circuit: Circuit) -> None:
    """Snapshot circuit code and detach work orders before deleting the circuit row."""
    db.execute(
        update(WorkOrder)
        .where(WorkOrder.circuit_id == circuit.id, WorkOrder.circuit_code.is_(None))
        .values(circuit_code=circuit.code)
    )
    db.execute(
        update(WorkOrder)
        .where(WorkOrder.circuit_id == circuit.id)
        .values(circuit_id=None)
    )


def delete_circuit_record(db: Session, circuit: Circuit) -> dict:
    """Purge overlay state, child rows, and the circuit itself."""
    if circuit.status not in DELETABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                "仅已拆除、草稿或失败状态的专线可删除；"
                "请先执行拆除工单后再删除"
            ),
        )
    _detach_work_orders(db, circuit)
    bugis_controller.purge_circuit(db, circuit)
    purged = purge_circuit_dependencies(db, circuit.id)
    code = circuit.code
    circuit_id = circuit.id
    db.delete(circuit)
    db.flush()
    return {
        "circuit_id": circuit_id,
        "circuit_code": code,
        "purged": purged,
    }


def delete_circuit_by_id(db: Session, circuit_id: int) -> dict:
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    return delete_circuit_record(db, circuit)
