"""Tests for scheduled SNMP interface discovery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.device import Device
from app.models.enums import Vendor
from app.models.platform_settings import PlatformSettings
from app.services import platform_settings as platform_cfg
from app.services import snmp_discovery_service


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _seed_device(db_session) -> Device:
    dev = Device(name="snmp-disc-sched", vendor=Vendor.H3C, mgmt_ip="10.0.0.88")
    db_session.add(dev)
    db_session.flush()
    return dev


def test_snmp_discover_interval_elapsed_without_history(db_session):
    plat = platform_cfg.get_or_create(db_session)
    plat.last_snmp_discover_at = None
    db_session.flush()
    assert snmp_discovery_service.interval_elapsed(db_session, 21600) is True


def test_snmp_discover_interval_not_elapsed(db_session):
    plat = platform_cfg.get_or_create(db_session)
    plat.last_snmp_discover_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db_session.flush()
    assert snmp_discovery_service.interval_elapsed(db_session, 21600) is False


def test_snmp_discover_due_after_six_hours(db_session):
    _seed_device(db_session)
    plat = platform_cfg.get_or_create(db_session)
    plat.snmp_discover_enabled = True
    plat.snmp_discover_interval_seconds = 21600
    plat.last_snmp_discover_at = datetime.now(timezone.utc) - timedelta(hours=7)
    db_session.commit()
    assert snmp_discovery_service.is_scheduled_discover_due(db_session) is True


def test_snmp_discover_not_due_when_disabled(db_session):
    plat = platform_cfg.get_or_create(db_session)
    plat.snmp_discover_enabled = False
    plat.last_snmp_discover_at = None
    db_session.commit()
    assert snmp_discovery_service.is_scheduled_discover_due(db_session) is False
