"""Fast purge of heavy circuit child rows before deleting the circuit row."""
from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.alarm import Alarm
from app.models.availability import CircuitAvailabilityEvent
from app.models.circuit_probe_log import CircuitProbeLog
from app.models.controlplane import DataPlaneBinding, EvpnRoute
from app.models.health_snapshot import CircuitHealthSnapshot
from app.models.telemetry import TelemetrySample


def purge_circuit_dependencies(db: Session, circuit_id: int) -> dict[str, int]:
    """Bulk-delete large child tables to avoid slow ORM cascades."""
    counts: dict[str, int] = {}

    def _wipe(label: str, stmt) -> None:
        result = db.execute(stmt)
        counts[label] = int(result.rowcount or 0)

    _wipe(
        "telemetry_samples",
        delete(TelemetrySample).where(TelemetrySample.circuit_id == circuit_id),
    )
    _wipe(
        "circuit_probe_logs",
        delete(CircuitProbeLog).where(CircuitProbeLog.circuit_id == circuit_id),
    )
    _wipe(
        "circuit_availability_events",
        delete(CircuitAvailabilityEvent).where(
            CircuitAvailabilityEvent.circuit_id == circuit_id
        ),
    )
    _wipe(
        "circuit_health_snapshots",
        delete(CircuitHealthSnapshot).where(
            CircuitHealthSnapshot.circuit_id == circuit_id
        ),
    )
    _wipe(
        "alarms",
        delete(Alarm).where(Alarm.circuit_id == circuit_id),
    )
    _wipe(
        "data_plane_bindings",
        delete(DataPlaneBinding).where(DataPlaneBinding.circuit_id == circuit_id),
    )
    _wipe(
        "evpn_routes",
        delete(EvpnRoute).where(EvpnRoute.circuit_id == circuit_id),
    )
    db.flush()
    return counts
