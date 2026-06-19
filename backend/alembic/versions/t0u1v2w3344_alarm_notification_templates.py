"""alarm notification templates JSON on platform_settings

Revision ID: t0u1v2w3344
Revises: s9t0u1v2233
Create Date: 2026-06-18

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "t0u1v2w3344_alarm_templates"
down_revision = "s9t0u1v2233_link_supplier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "platform_settings",
        sa.Column("alarm_notification_templates", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("platform_settings", "alarm_notification_templates")
