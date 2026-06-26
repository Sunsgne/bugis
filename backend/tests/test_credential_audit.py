"""Southbound credential audit."""
from __future__ import annotations

import uuid

import pytest

from app.models.device import Device
from app.models.enums import DeviceStatus, Vendor
from app.services.credential_audit_service import audit_all_devices, audit_device
from app.services.credential_store import encrypt_value


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _device(db_session, *, password: str | None = "secret") -> Device:
    suffix = uuid.uuid4().hex[:8]
    device = Device(
        name=f"DEV-{suffix}",
        vendor=Vendor.H3C,
        status=DeviceStatus.ONLINE,
        mgmt_ip="10.0.0.1",
        username="ops",
        password=encrypt_value(password) if password else None,
        snmp_enabled=False,
    )
    db_session.add(device)
    db_session.commit()
    return device


def test_audit_device_ok(db_session):
    device = _device(db_session)
    row = audit_device(device)
    assert row["ok"] is True
    assert row["issues"] == []


def test_audit_device_decrypt_failed(db_session, monkeypatch):
    device = _device(db_session)
    device.password = "enc$invalid-ciphertext"
    row = audit_device(device)
    assert row["ok"] is False
    assert any(i["problem"] == "decrypt_failed" for i in row["issues"])


def test_audit_device_missing_ssh_password(db_session):
    device = _device(db_session, password=None)
    row = audit_device(device)
    assert row["ok"] is False
    assert any(i["field"] == "password" and i["problem"] == "missing" for i in row["issues"])


def test_audit_all_devices_lists_unhealthy_only(db_session):
    bad = _device(db_session, password=None)
    report = audit_all_devices(db_session)
    bad_rows = [d for d in report["devices"] if d["device_id"] == bad.id]
    assert len(bad_rows) == 1
    assert bad_rows[0]["ok"] is False
