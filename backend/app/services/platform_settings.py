"""Load, persist and apply platform settings (operational + branding)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.platform_settings import PlatformSettings
from app.schemas.platform_settings import (
    BrandingOut,
    BrandingUpdate,
    PlatformSettingsOut,
    PlatformSettingsUpdate,
)


def _defaults_from_env() -> dict:
    return {
        "dry_run": settings.dry_run,
        "netconf_timeout": settings.netconf_timeout,
        "baseline_ntp_server": settings.baseline_ntp_server,
        "baseline_syslog_server": settings.baseline_syslog_server,
        "scheduler_enabled": settings.scheduler_enabled,
        "scheduler_interval_seconds": settings.scheduler_interval_seconds,
        "threshold_packet_loss_pct": settings.threshold_packet_loss_pct,
        "threshold_latency_ms": settings.threshold_latency_ms,
        "threshold_utilization_pct": settings.threshold_utilization_pct,
        "threshold_health_score": settings.threshold_health_score,
        "threshold_link_utilization_pct": settings.threshold_link_utilization_pct,
        "controller_bgp_asn": settings.controller_bgp_asn,
        "controller_node_id": settings.controller_node_id,
        "webhook_token": settings.webhook_token,
        "smtp_host": settings.smtp_host,
        "smtp_port": settings.smtp_port,
        "smtp_user": settings.smtp_user,
        "smtp_password": settings.smtp_password or None,
        "smtp_from": settings.smtp_from,
        "smtp_provider": settings.smtp_provider,
        "smtp_security": settings.smtp_security,
        "enable_metrics": settings.enable_metrics,
        "access_token_expire_minutes": settings.access_token_expire_minutes,
    }


def _branding_defaults() -> dict:
    return {
        "product_name": "Bugis Network",
        "header_title": "DCI / EVPN 全域网络运营中枢",
        "tagline": "DCI · EVPN 全域智能运营",
        "login_title": "Bugis Network",
        "login_subtitle": "Multi-Vendor · BGP EVPN · Intelligent Fabric Ops",
        "hero_title": "DCI / EVPN 运营驾驶舱",
        "hero_subtitle": "多厂商异构 · VXLAN / SR-MPLS EVPN · 自研 SDN · 跨域 DCI",
        "accent_color": "#52c41a",
        "login_background": "linear-gradient(135deg, #0b1f3a 0%, #1677ff 100%)",
    }


def sync_to_runtime(row: PlatformSettings) -> None:
    """Push DB settings into the in-process Settings object used by services."""
    settings.dry_run = row.dry_run
    settings.netconf_timeout = row.netconf_timeout
    settings.baseline_ntp_server = row.baseline_ntp_server
    settings.baseline_syslog_server = row.baseline_syslog_server
    settings.scheduler_enabled = row.scheduler_enabled
    settings.scheduler_interval_seconds = row.scheduler_interval_seconds
    settings.threshold_packet_loss_pct = row.threshold_packet_loss_pct
    settings.threshold_latency_ms = row.threshold_latency_ms
    settings.threshold_utilization_pct = row.threshold_utilization_pct
    settings.threshold_health_score = row.threshold_health_score
    settings.threshold_link_utilization_pct = row.threshold_link_utilization_pct
    settings.controller_bgp_asn = row.controller_bgp_asn
    settings.controller_node_id = row.controller_node_id
    settings.webhook_token = row.webhook_token
    settings.smtp_host = row.smtp_host
    settings.smtp_port = row.smtp_port
    settings.smtp_user = row.smtp_user
    if row.smtp_password:
        settings.smtp_password = row.smtp_password
    settings.smtp_from = row.smtp_from
    settings.smtp_provider = row.smtp_provider
    settings.smtp_security = row.smtp_security or "starttls"
    settings.enable_metrics = row.enable_metrics
    settings.access_token_expire_minutes = row.access_token_expire_minutes

    from app import scheduler

    scheduler.set_interval(row.scheduler_interval_seconds)


def get_or_create(db: Session) -> PlatformSettings:
    row = db.get(PlatformSettings, 1)
    if row:
        return row
    row = PlatformSettings(id=1, **_defaults_from_env(), **_branding_defaults())
    db.add(row)
    db.commit()
    db.refresh(row)
    sync_to_runtime(row)
    return row


def to_branding(row: PlatformSettings) -> BrandingOut:
    return BrandingOut.model_validate(row, from_attributes=True)


def to_out(row: PlatformSettings) -> PlatformSettingsOut:
    data = PlatformSettingsOut.model_validate(row, from_attributes=True)
    return data.model_copy(
        update={
            "smtp_password_set": bool(row.smtp_password),
            "smtp_password": None,
        }
    )


def update_settings(db: Session, payload: PlatformSettingsUpdate) -> PlatformSettings:
    row = get_or_create(db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "smtp_password" and value == "":
            continue
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    sync_to_runtime(row)
    return row


def update_branding(db: Session, payload: BrandingUpdate) -> PlatformSettings:
    row = get_or_create(db)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key in ("logo_url", "logo_mark_url") and value == "":
            value = None
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row
