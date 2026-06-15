"""Idempotent demo enrichments (safe on every deploy).

- Ensures platform/SNMP singleton rows exist
- Activates up to two draft circuits when none are active (legacy demo DBs)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.bootstrap import ensure_platform_settings, ensure_snmp_settings, ensure_superuser
from app.core.database import SessionLocal, init_db
from app.models.circuit import Circuit
from app.models.enums import CircuitStatus


def run() -> None:
    init_db()
    db = SessionLocal()
    try:
        ensure_superuser(db)
        ensure_snmp_settings(db)
        ensure_platform_settings(db)

        active = db.execute(
            select(Circuit).where(Circuit.status == CircuitStatus.ACTIVE)
        ).scalars().all()
        if active:
            print(f"Demo state OK ({len(active)} active circuits).")
            return

        drafts = db.execute(
            select(Circuit)
            .where(Circuit.status == CircuitStatus.DRAFT)
            .order_by(Circuit.id)
            .limit(2)
        ).scalars().all()
        if not drafts:
            print("No circuits to activate.")
            return

        for c in drafts:
            c.status = CircuitStatus.ACTIVE
        db.commit()
        names = ", ".join(c.name for c in drafts)
        print(f"Activated demo circuits: {names}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
