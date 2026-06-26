"""Circuit alarm grace period and per-kind enablement."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "z6a7b8c9900"
down_revision = "y5z6a7b8899"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("circuits", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "alarm_suppress_minutes",
                sa.Integer(),
                nullable=False,
                server_default="60",
            )
        )
        batch_op.add_column(
            sa.Column("enabled_alarm_kinds", sa.Text(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("circuits", schema=None) as batch_op:
        batch_op.drop_column("enabled_alarm_kinds")
        batch_op.drop_column("alarm_suppress_minutes")
        batch_op.drop_column("activated_at")
