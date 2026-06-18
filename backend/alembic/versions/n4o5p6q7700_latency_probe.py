"""Per-circuit latency probe enable switch."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "n4o5p6q7700_latency_probe"
down_revision = "m3n4o5p6600_link_alarm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("circuits", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "latency_probe_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("circuits", schema=None) as batch_op:
        batch_op.drop_column("latency_probe_enabled")
