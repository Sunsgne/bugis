"""Idempotent demo enrichments (safe on every deploy)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import ensure_platform_settings, ensure_snmp_settings, ensure_superuser
from app.core.database import SessionLocal, init_db
from scripts.demo_data import activate_draft_circuits, backfill_demo_circuits


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
            return

        print("Demo state OK.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
