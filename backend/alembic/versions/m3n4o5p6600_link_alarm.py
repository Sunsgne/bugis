"""Per-link utilization alarm threshold override."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "m3n4o5p6600_link_alarm"
down_revision = "l2m3n4o5500_circuit_alarm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("links", schema=None) as batch_op:
        batch_op.add_column(sa.Column("alarm_utilization_pct", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("links", schema=None) as batch_op:
        batch_op.drop_column("alarm_utilization_pct")
