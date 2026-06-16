"""Idempotent demo enrichments (safe on every deploy)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import ensure_platform_settings, ensure_snmp_settings, ensure_superuser
from app.core.database import SessionLocal, init_db
from scripts.demo_data import (
    activate_draft_circuits,
    backfill_demo_circuits,
    ensure_active_demo_circuit,
    sync_active_circuit_controlplane,
)


def run() -> None:
    init_db()
    db = SessionLocal()
    try:
        ensure_superuser(db)
        ensure_snmp_settings(db)
        ensure_platform_settings(db)

        added = backfill_demo_circuits(db)
        if added:
            print(f"Backfilled {added} demo circuits.")
            return

        activated = activate_draft_circuits(db)
        if activated:
            print(f"Activated {activated} draft circuits for demo monitoring.")

        restored = ensure_active_demo_circuit(db)
        if restored:
            print(f"Restored {restored} active demo circuit(s).")

        synced = sync_active_circuit_controlplane(db)
        if synced:
            print(f"Synced EVPN control plane for {synced} active circuits.")
            return

        if activated or restored:
            return

        print("Demo state OK.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
