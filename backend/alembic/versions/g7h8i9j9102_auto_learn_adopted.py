"""Periodic auto-learn settings and adopted circuit flag."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "g7h8i9j9102_auto_learn_adopted"
down_revision = "f6a7b8c9081_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platform_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("auto_learn_enabled", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column(
                "auto_learn_interval_seconds",
                sa.Integer(),
                nullable=False,
                server_default="60",
            )
        )
    with op.batch_alter_table("circuits", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("adopted", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("circuits", schema=None) as batch_op:
        batch_op.drop_column("adopted")
    with op.batch_alter_table("platform_settings", schema=None) as batch_op:
        batch_op.drop_column("auto_learn_interval_seconds")
        batch_op.drop_column("auto_learn_enabled")
