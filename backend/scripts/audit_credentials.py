"""Audit device / SNMP credentials (detect decrypt failures after SECRET_KEY rotation).

Usage (from backend dir or container):
  python -m scripts.audit_credentials
"""
from __future__ import annotations

import json
import sys

from app.core.database import SessionLocal
from app.services.credential_audit_service import audit_all_devices


def main() -> None:
    db = SessionLocal()
    try:
        report = audit_all_devices(db)
    finally:
        db.close()

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["unhealthy"] or report.get("platform_snmp"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
