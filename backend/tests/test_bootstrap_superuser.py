"""Bootstrap admin must not reappear after operators delete it."""
from __future__ import annotations

import uuid

import pytest

from app.bootstrap import ensure_superuser
from app.core.config import settings
from app.core.security import hash_password
from app.models.enums import UserRole, UserScope
from app.models.user import User


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def test_ensure_superuser_skips_when_other_platform_admin_exists(db_session):
    suffix = uuid.uuid4().hex[:8]
    for user in db_session.query(User).filter(User.username == settings.first_superuser).all():
        db_session.delete(user)
    db_session.add(
        User(
            username=f"ops-{suffix}",
            full_name="Ops Lead",
            role=UserRole.ADMIN,
            scope=UserScope.PLATFORM,
            hashed_password=hash_password("strongpass1"),
            is_active=True,
        )
    )
    db_session.commit()

    ensure_superuser(db_session)

    admin = db_session.query(User).filter(User.username == settings.first_superuser).first()
    assert admin is None


def test_ensure_superuser_is_idempotent(db_session):
    before = db_session.query(User).filter(User.username == settings.first_superuser).count()
    ensure_superuser(db_session)
    ensure_superuser(db_session)
    after = db_session.query(User).filter(User.username == settings.first_superuser).count()
    assert after == before
    assert after >= 1
