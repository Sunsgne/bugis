"""Platform settings with customizable branding."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f4a5b6c9076"
down_revision = "e5f9b2c9041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_name", sa.String(length=128), nullable=False, server_default="Bugis Network"),
        sa.Column("header_title", sa.String(length=255), nullable=False, server_default="DCI / EVPN 全域网络运营中枢"),
        sa.Column("tagline", sa.String(length=255), nullable=False, server_default="DCI · EVPN 全域智能运营"),
        sa.Column("login_title", sa.String(length=128), nullable=False, server_default="Bugis Network"),
        sa.Column("login_subtitle", sa.String(length=255), nullable=False, server_default="Multi-Vendor · BGP EVPN · Intelligent Fabric Ops"),
        sa.Column("hero_title", sa.String(length=255), nullable=False, server_default="DCI / EVPN 运营驾驶舱"),
        sa.Column("hero_subtitle", sa.String(length=512), nullable=False, server_default="多厂商异构 · VXLAN / SR-MPLS EVPN · 自研 SDN · 跨域 DCI"),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("logo_mark_url", sa.Text(), nullable=True),
        sa.Column("accent_color", sa.String(length=16), nullable=False, server_default="#52c41a"),
        sa.Column("login_background", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("platform_settings")
