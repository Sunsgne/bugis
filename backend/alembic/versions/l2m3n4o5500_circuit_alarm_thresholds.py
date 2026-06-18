"""Per-circuit SLA alarm thresholds (override platform defaults when set)."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "l2m3n4o5500_circuit_alarm"
down_revision = "k1l2m3n4400_encrypt_cred_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("circuits", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("alarm_latency_ms", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("alarm_packet_loss_pct", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("alarm_utilization_pct", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("alarm_health_score_min", sa.Float(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("circuits", schema=None) as batch_op:
        batch_op.drop_column("alarm_health_score_min")
        batch_op.drop_column("alarm_utilization_pct")
        batch_op.drop_column("alarm_packet_loss_pct")
        batch_op.drop_column("alarm_latency_ms")
