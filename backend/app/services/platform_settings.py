"""Load and persist platform settings (branding singleton)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.platform_settings import PlatformSettings
from app.schemas.platform_settings import BrandingOut, BrandingUpdate, PlatformSettingsOut


def _defaults() -> dict:
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


def get_or_create(db: Session) -> PlatformSettings:
    row = db.get(PlatformSettings, 1)
    if row:
        return row
    row = PlatformSettings(id=1, **_defaults())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def to_branding(row: PlatformSettings) -> BrandingOut:
    return BrandingOut.model_validate(row, from_attributes=True)


def to_out(row: PlatformSettings) -> PlatformSettingsOut:
    return PlatformSettingsOut.model_validate(row, from_attributes=True)


def update_branding(db: Session, payload: BrandingUpdate) -> PlatformSettings:
    row = get_or_create(db)
    data = payload.model_dump(exclude_unset=True)
    # Allow clearing logo fields explicitly.
    for key, value in data.items():
        if key in ("logo_url", "logo_mark_url") and value == "":
            value = None
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row
