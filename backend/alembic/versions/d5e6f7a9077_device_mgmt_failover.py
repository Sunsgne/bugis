"""Device dual management IP and probe persistence."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d5e6f7a9077_device_mgmt_failover"
down_revision = "c4d5e6f9076_telemetry_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.add_column(sa.Column("mgmt_ip_backup", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("mgmt_ip_primary_label", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("mgmt_ip_backup_label", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("mgmt_ip_active", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("mgmt_ip_active_role", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("last_reachability_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_reachability_latency_ms", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("last_reachability_method", sa.String(length=32), nullable=True))

    op.create_table(
        "circuit_probe_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("circuit_id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("probe_method", sa.String(length=32), nullable=True),
        sa.Column("reachable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("rtt_ms", sa.Float(), nullable=True),
        sa.Column("jitter_ms", sa.Float(), nullable=True),
        sa.Column("packet_loss_pct", sa.Float(), nullable=True),
        sa.Column("path_mode", sa.String(length=32), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["circuit_id"], ["circuits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_circuit_probe_logs_circuit_id", "circuit_probe_logs", ["circuit_id"])


def downgrade() -> None:
    op.drop_index("ix_circuit_probe_logs_circuit_id", table_name="circuit_probe_logs")
    op.drop_table("circuit_probe_logs")
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.drop_column("last_reachability_method")
        batch_op.drop_column("last_reachability_latency_ms")
        batch_op.drop_column("last_reachability_at")
        batch_op.drop_column("mgmt_ip_active_role")
        batch_op.drop_column("mgmt_ip_active")
        batch_op.drop_column("mgmt_ip_backup_label")
        batch_op.drop_column("mgmt_ip_primary_label")
        batch_op.drop_column("mgmt_ip_backup")
