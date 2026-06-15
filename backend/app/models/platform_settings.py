"""Platform-wide settings (singleton row), including customizable branding."""
from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class PlatformSettings(Base, TimestampMixin):
    """Editable platform parameters; row id=1 is the singleton."""

    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    product_name: Mapped[str] = mapped_column(String(128), default="Bugis Network")
    header_title: Mapped[str] = mapped_column(
        String(255), default="DCI / EVPN 全域网络运营中枢"
    )
    tagline: Mapped[str] = mapped_column(
        String(255), default="DCI · EVPN 全域智能运营"
    )
    login_title: Mapped[str] = mapped_column(String(128), default="Bugis Network")
    login_subtitle: Mapped[str] = mapped_column(
        String(255), default="Multi-Vendor · BGP EVPN · Intelligent Fabric Ops"
    )
    hero_title: Mapped[str] = mapped_column(
        String(255), default="DCI / EVPN 运营驾驶舱"
    )
    hero_subtitle: Mapped[str] = mapped_column(
        String(512),
        default="多厂商异构 · VXLAN / SR-MPLS EVPN · 自研 SDN · 跨域 DCI",
    )
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_mark_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    accent_color: Mapped[str] = mapped_column(String(16), default="#52c41a")
    login_background: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default="linear-gradient(135deg, #0b1f3a 0%, #1677ff 100%)",
    )
