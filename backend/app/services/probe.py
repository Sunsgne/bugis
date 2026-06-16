"""Active circuit path probe (on-demand connectivity test).

Delegates to ``circuit_probe`` for path-aligned fabric + EVPN service-plane
probes. When ``dry_run`` is enabled, returns explicitly labeled simulated metrics.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.circuit import Circuit
from app.services.circuit_probe import probe_circuit as _probe_circuit


def probe_circuit(db: Session, circuit: Circuit) -> dict:
    return _probe_circuit(db, circuit)
