"""Device learn runs + auto_learn_on_import platform flag."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f9065"
down_revision = "b2c3d4e9054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_learn_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="success"),
        sa.Column("snapshot_id", sa.Integer(), nullable=True),
        sa.Column("inventory", sa.JSON(), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["device_config_snapshots.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_device_learn_runs_device_id", "device_learn_runs", ["device_id"])
    op.create_index("ix_device_learn_runs_id", "device_learn_runs", ["id"])
    op.add_column(
        "platform_settings",
        sa.Column("auto_learn_on_import", sa.Boolean(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("platform_settings", "auto_learn_on_import")
    op.drop_index("ix_device_learn_runs_id", table_name="device_learn_runs")
    op.drop_index("ix_device_learn_runs_device_id", table_name="device_learn_runs")
    op.drop_table("device_learn_runs")
