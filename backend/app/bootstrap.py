"""Bootstrap helpers: ensure an initial admin user and built-in controller exist."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.controller.engine import CONTROLLER_VERSION
from app.core.config import settings
from app.core.security import hash_password
from app.models.controller import Controller
from app.models.enums import ControllerType, UserRole, UserScope
from app.models.tenant import Tenant
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
        scope=UserScope.PLATFORM,
        hashed_password=hash_password(settings.first_superuser_password),
        is_active=True,
    )
    db.add(user)
    db.commit()


def ensure_tenant_portal_demo_user(
    db: Session,
    *,
    tenant_code: str = "BANK01",
    username: str | None = None,
    password: str | None = None,
) -> User | None:
    """Ensure a demo tenant portal account exists (idempotent).

    Credentials are sourced from BUGIS_PORTAL_USER / BUGIS_PORTAL_PASS so no
    secrets are hardcoded in the repository. Demo seeding only runs when
    BUGIS_RUN_DEMO is enabled.
    """
    import os

    username = username or os.environ.get("BUGIS_PORTAL_USER", "bank_portal")
    password = password or os.environ.get("BUGIS_PORTAL_PASS", "change-me-portal-password")
    tenant = db.execute(
        select(Tenant).where(Tenant.code == tenant_code)
    ).scalar_one_or_none()
    if not tenant:
        return None
    existing = db.execute(
        select(User).where(User.username == username)
    ).scalar_one_or_none()
    if existing:
        return existing
    user = User(
        username=username,
        full_name=f"{tenant.name} · 门户",
        role=UserRole.TENANT_VIEWER,
        scope=UserScope.TENANT,
        tenant_id=tenant.id,
        hashed_password=hash_password(password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def ensure_snmp_settings(db: Session) -> None:
    from app.services import snmp_settings

    snmp_settings.get_or_create(db)


def ensure_platform_settings(db: Session) -> None:
    from app.services import platform_settings

    row = platform_settings.get_or_create(db)
    platform_settings.sync_to_runtime(row)


def encrypt_credentials_at_rest(db: Session) -> None:
    """One-time migration: encrypt plaintext device/controller/SNMP secrets."""
    from app.models.device import Device
    from app.models.snmp_settings import SnmpSettings
    from app.services.credential_store import (
        encrypt_device_model,
        encrypt_value,
        is_encrypted,
    )

    changed = False
    for device in db.execute(select(Device)).scalars():
        before = (
            device.password,
            device.enable_password,
            device.snmp_community,
            device.snmp_v3_auth_password,
            device.snmp_v3_priv_password,
        )
        encrypt_device_model(device)
        after = (
            device.password,
            device.enable_password,
            device.snmp_community,
            device.snmp_v3_auth_password,
            device.snmp_v3_priv_password,
        )
        if before != after:
            changed = True

    for ctrl in db.execute(select(Controller)).scalars():
        if ctrl.password and not is_encrypted(ctrl.password):
            ctrl.password = encrypt_value(ctrl.password)
            changed = True

    snmp = db.get(SnmpSettings, 1)
    if snmp:
        for field in ("community", "write_community", "v3_auth_password", "v3_priv_password"):
            val = getattr(snmp, field, None)
            if val and not is_encrypted(val):
                setattr(snmp, field, encrypt_value(val))
                changed = True

    if changed:
        db.commit()
