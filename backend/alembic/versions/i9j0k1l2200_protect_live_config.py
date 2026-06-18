"""Add protect_live_config platform setting (live-config overwrite protection)."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "i9j0k1l2200_protect_live_config"
down_revision = "h8i9j0k1123_security_mfa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platform_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "protect_live_config",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("platform_settings", schema=None) as batch_op:
        batch_op.drop_column("protect_live_config")
