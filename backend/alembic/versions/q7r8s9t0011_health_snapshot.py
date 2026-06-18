"""circuit_health_snapshots for portal-scale health reads.

Revision ID: q7r8s9t0011
Revises: p6q7r8s9900
Create Date: 2026-06-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "q7r8s9t0011"
down_revision = "p6q7r8s9900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "circuit_health_snapshots",
        sa.Column("circuit_id", sa.Integer(), nullable=False),
        sa.Column("health_score", sa.Float(), nullable=False, server_default="100"),
        sa.Column("avg_latency_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_jitter_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_packet_loss_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_utilization_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("peak_utilization_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tunnel_down", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("qos_samples", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("samples", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["circuit_id"], ["circuits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("circuit_id"),
    )
    op.create_index(
        "ix_health_snapshots_updated",
        "circuit_health_snapshots",
        ["updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_health_snapshots_updated", table_name="circuit_health_snapshots")
    op.drop_table("circuit_health_snapshots")
