"""SNMP community must not fall back to enc$ ciphertext."""
from __future__ import annotations

import pytest

from app.services.credential_store import encrypt_value, is_encrypted
from app.services.snmp_settings import _resolved_secret, effective_community


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def test_resolved_secret_never_returns_ciphertext():
    raw = encrypt_value("my-community") or "enc$fake"
    assert is_encrypted(raw)
    bad = _resolved_secret("enc$not-valid-fernet-token", default="public")
    assert bad == "public"


def test_effective_community_uses_plaintext_when_decrypt_ok(db_session):
    from app.models.device import Device
    from app.models.enums import DeviceStatus, Vendor
    from app.services import snmp_settings as snmp_cfg

    cfg = snmp_cfg.get_or_create(db_session)
    cfg.community = encrypt_value("zenlenet-ro")
    db_session.commit()
    device = Device(
        name="SNMP-DEV",
        vendor=Vendor.H3C,
        status=DeviceStatus.ONLINE,
        mgmt_ip="10.0.0.2",
        snmp_enabled=True,
    )
    assert effective_community(db_session, device) == "zenlenet-ro"
