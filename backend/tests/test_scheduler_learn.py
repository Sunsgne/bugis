"""Tests for scheduled config pull timing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.device import Device
from app.models.device_learn_run import DeviceLearnRun
from app.models.enums import Vendor
from app.scheduler import _is_scheduled_learn_due, _learn_interval_elapsed
from app.services import platform_settings as platform_cfg
import pytest


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
    dev = Device(name="learn-sched-test", vendor=Vendor.H3C, mgmt_ip="10.0.0.99")
    db_session.add(dev)
    db_session.flush()
    return dev


def test_learn_interval_elapsed_without_history(db_session):
    assert _learn_interval_elapsed(db_session, 3600) is True


def test_learn_interval_not_elapsed(db_session):
    dev = _seed_device(db_session)
    db_session.add(
        DeviceLearnRun(
            device_id=dev.id,
            status="success",
            created_by="scheduler",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
    )
    db_session.commit()
    assert _learn_interval_elapsed(db_session, 3600) is False


def test_learn_due_respects_platform_interval(db_session):
    db_session.query(DeviceLearnRun).delete()
    dev = _seed_device(db_session)
    plat = platform_cfg.get_or_create(db_session)
    plat.auto_learn_enabled = True
    plat.auto_learn_interval_seconds = 3600
    db_session.add(
        DeviceLearnRun(
            device_id=dev.id,
            status="success",
            created_by="scheduler",
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
    )
    db_session.commit()
    assert _is_scheduled_learn_due(db_session) is True


def test_learn_not_due_when_disabled(db_session):
    plat = platform_cfg.get_or_create(db_session)
    plat.auto_learn_enabled = False
    plat.auto_learn_interval_seconds = 60
    db_session.commit()
    assert _is_scheduled_learn_due(db_session) is False
