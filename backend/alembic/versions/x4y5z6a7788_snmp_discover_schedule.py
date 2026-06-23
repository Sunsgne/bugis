"""Scheduled SNMP interface discovery settings."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "x4y5z6a7788"
down_revision = "w3x4y5z6677"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platform_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "snmp_discover_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "snmp_discover_interval_seconds",
                sa.Integer(),
                nullable=False,
                server_default="21600",
            )
        )
        batch_op.add_column(
            sa.Column("last_snmp_discover_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("platform_settings", schema=None) as batch_op:
        batch_op.drop_column("last_snmp_discover_at")
        batch_op.drop_column("snmp_discover_interval_seconds")
        batch_op.drop_column("snmp_discover_enabled")
