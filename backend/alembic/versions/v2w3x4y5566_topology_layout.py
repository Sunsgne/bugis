"""topology node layout JSON on platform_settings

Revision ID: v2w3x4y5566
Revises: u1v2w3x4455_wo_retention
Create Date: 2026-06-18

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v2w3x4y5566"
down_revision = "u1v2w3x4455_wo_retention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "platform_settings",
        sa.Column("topology_layout", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("platform_settings", "topology_layout")
