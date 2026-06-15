"""Switch platform default from dry-run to production mode."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e9055_prod_mode"
down_revision = "a1b2c3d9044_mgmt_ifaces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE platform_settings SET dry_run = false WHERE id = 1")
    op.alter_column(
        "platform_settings",
        "dry_run",
        existing_type=sa.Boolean(),
        server_default=sa.text("false"),
    )


def downgrade() -> None:
    op.alter_column(
        "platform_settings",
        "dry_run",
        existing_type=sa.Boolean(),
        server_default=sa.text("true"),
    )
    op.execute("UPDATE platform_settings SET dry_run = true WHERE id = 1")
