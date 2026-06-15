"""Add branding columns to platform_settings."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f4a5b6c9076"
down_revision = "c3d4e5f9065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "platform_settings",
        sa.Column("product_name", sa.String(length=128), nullable=False, server_default="Bugis Network"),
    )
    op.add_column(
        "platform_settings",
        sa.Column("header_title", sa.String(length=255), nullable=False, server_default="DCI / EVPN 全域网络运营中枢"),
    )
    op.add_column(
        "platform_settings",
        sa.Column("tagline", sa.String(length=255), nullable=False, server_default="DCI · EVPN 全域智能运营"),
    )
    op.add_column(
        "platform_settings",
        sa.Column("login_title", sa.String(length=128), nullable=False, server_default="Bugis Network"),
    )
    op.add_column(
        "platform_settings",
        sa.Column("login_subtitle", sa.String(length=255), nullable=False, server_default="Multi-Vendor · BGP EVPN · Intelligent Fabric Ops"),
    )
    op.add_column(
        "platform_settings",
        sa.Column("hero_title", sa.String(length=255), nullable=False, server_default="DCI / EVPN 运营驾驶舱"),
    )
    op.add_column(
        "platform_settings",
        sa.Column("hero_subtitle", sa.String(length=512), nullable=False, server_default="多厂商异构 · VXLAN / SR-MPLS EVPN · 自研 SDN · 跨域 DCI"),
    )
    op.add_column("platform_settings", sa.Column("logo_url", sa.Text(), nullable=True))
    op.add_column("platform_settings", sa.Column("logo_mark_url", sa.Text(), nullable=True))
    op.add_column(
        "platform_settings",
        sa.Column("accent_color", sa.String(length=16), nullable=False, server_default="#52c41a"),
    )
    op.add_column("platform_settings", sa.Column("login_background", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("platform_settings", "login_background")
    op.drop_column("platform_settings", "accent_color")
    op.drop_column("platform_settings", "logo_mark_url")
    op.drop_column("platform_settings", "logo_url")
    op.drop_column("platform_settings", "hero_subtitle")
    op.drop_column("platform_settings", "hero_title")
    op.drop_column("platform_settings", "login_subtitle")
    op.drop_column("platform_settings", "login_title")
    op.drop_column("platform_settings", "tagline")
    op.drop_column("platform_settings", "header_title")
    op.drop_column("platform_settings", "product_name")
