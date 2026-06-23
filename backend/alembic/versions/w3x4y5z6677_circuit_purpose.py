"""Add circuit purpose (business vs test)

Revision ID: w3x4y5z6677
Revises: v2w3x4y5566
Create Date: 2026-06-23

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "w3x4y5z6677"
down_revision = "v2w3x4y5566"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "circuits",
        sa.Column(
            "purpose",
            sa.String(length=16),
            nullable=False,
            server_default="business",
        ),
    )
    op.alter_column("circuits", "purpose", server_default=None)


def downgrade() -> None:
    op.drop_column("circuits", "purpose")
