"""Add supplier to backbone links."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "s9t0u1v2233_link_supplier"
down_revision = "r8s9t0u1122"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("links", schema=None) as batch_op:
        batch_op.add_column(sa.Column("supplier", sa.String(length=128), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("links", schema=None) as batch_op:
        batch_op.drop_column("supplier")
