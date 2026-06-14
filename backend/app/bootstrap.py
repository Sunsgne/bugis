"""Bootstrap helpers: ensure an initial admin user exists."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User


def ensure_superuser(db: Session) -> None:
    existing = db.execute(
        select(User).where(User.username == settings.first_superuser)
    ).scalar_one_or_none()
    if existing:
        return
    user = User(
        username=settings.first_superuser,
        full_name="Platform Administrator",
        role=UserRole.ADMIN,
        hashed_password=hash_password(settings.first_superuser_password),
        is_active=True,
    )
    db.add(user)
    db.commit()
