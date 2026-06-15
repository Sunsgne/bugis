"""Optional per-device SNMP collection settings."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a5b6c7d9087"
down_revision = "f4a5b6c9076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("snmp_enabled", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.add_column(
        "devices",
        sa.Column("snmp_port", sa.Integer(), nullable=False, server_default="161"),
    )
    op.add_column(
        "devices",
        sa.Column("snmp_community", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "devices",
        sa.Column("snmp_version", sa.String(length=8), nullable=False, server_default="2c"),
    )


def downgrade() -> None:
    op.drop_column("devices", "snmp_version")
    op.drop_column("devices", "snmp_community")
    op.drop_column("devices", "snmp_port")
    op.drop_column("devices", "snmp_enabled")
