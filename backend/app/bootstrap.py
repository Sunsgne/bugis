"""Bootstrap helpers: ensure an initial admin user and built-in controller exist."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.controller.engine import CONTROLLER_VERSION
from app.core.config import settings
from app.core.security import hash_password
from app.models.controller import Controller
from app.models.enums import ControllerType, UserRole
from app.models.user import User


def ensure_bugis_controller(db: Session) -> Controller:
    """Register the built-in Bugis SDN controller (idempotent)."""
    existing = db.execute(
        select(Controller).where(Controller.type == ControllerType.BUGIS)
    ).scalar_one_or_none()
    if existing:
        existing.description = (
            f"平台内置自研 EVPN 控制平面 v{CONTROLLER_VERSION}，"
            "无需手动添加或配置北向地址"
        )
        db.commit()
        db.refresh(existing)
        return existing
    controller = Controller(
        name="Bugis SDN 控制器",
        type=ControllerType.BUGIS,
        base_url="internal://bugis",
        username="-",
        description=(
            f"平台内置自研 EVPN 控制平面 v{CONTROLLER_VERSION}，"
            "无需手动添加或配置北向地址"
        ),
    )
    db.add(controller)
    db.commit()
    db.refresh(controller)
    return controller


def ensure_cluster_node(db: Session) -> None:
    from app.controller import ha

    ha.ensure_local_node(db, node_id=settings.controller_node_id)
    db.commit()


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
