"""Add circuit_endpoints.interface_description for device S-VID desc."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c4d5e6f9078_iface_desc"
down_revision = "b2c3d4e9055_prod_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("circuit_endpoints", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("interface_description", sa.String(length=255), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("circuit_endpoints", schema=None) as batch_op:
        batch_op.drop_column("interface_description")
