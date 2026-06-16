"""Add tenant portal user scope and tenant_id on users."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e6f7a8b9080_tenant_portal"
down_revision = "b2c3d4e9055_prod_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "scope",
                sa.String(length=32),
                nullable=False,
                server_default="platform",
            )
        )
        batch_op.add_column(
            sa.Column("tenant_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_users_tenant_id_tenants",
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_users_tenant_id", ["tenant_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_tenant_id")
        batch_op.drop_constraint("fk_users_tenant_id_tenants", type_="foreignkey")
        batch_op.drop_column("tenant_id")
        batch_op.drop_column("scope")
