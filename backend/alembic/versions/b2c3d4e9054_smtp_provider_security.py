"""Add smtp_provider and smtp_security to platform_settings."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e9054"
down_revision = "a1b2c3d9043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "platform_settings",
        sa.Column("smtp_provider", sa.String(length=64), nullable=False, server_default=""),
    )
    op.add_column(
        "platform_settings",
        sa.Column("smtp_security", sa.String(length=16), nullable=False, server_default="starttls"),
    )


def downgrade() -> None:
    op.drop_column("platform_settings", "smtp_security")
    op.drop_column("platform_settings", "smtp_provider")
