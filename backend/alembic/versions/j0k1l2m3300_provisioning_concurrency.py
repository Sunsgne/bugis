"""Provisioning concurrency + pre-change snapshot platform settings.

Adds:
  * snapshot_before_change  — auto-capture live running-config before a change
  * async_provisioning      — run provision/teardown work orders on a worker
  * provision_max_concurrency — parallel device pushes the worker performs
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "j0k1l2m3300_provisioning_concurrency"
down_revision = "i9j0k1l2200_protect_live_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platform_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "snapshot_before_change",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "async_provisioning",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "provision_max_concurrency",
                sa.Integer(),
                nullable=False,
                server_default="4",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("platform_settings", schema=None) as batch_op:
        batch_op.drop_column("provision_max_concurrency")
        batch_op.drop_column("async_provisioning")
        batch_op.drop_column("snapshot_before_change")
