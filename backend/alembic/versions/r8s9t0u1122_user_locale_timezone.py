"""Add per-user locale and timezone preferences.

Revision ID: r8s9t0u1122
Revises: q7r8s9t0011
Create Date: 2026-06-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "r8s9t0u1122"
down_revision = "q7r8s9t0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("locale", sa.String(length=8), nullable=False, server_default="zh"),
    )
    op.add_column(
        "users",
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="Asia/Shanghai",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "timezone")
    op.drop_column("users", "locale")
