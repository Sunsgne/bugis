"""remote ipt service type and circuit egress fields

Revision ID: b1c4e8f92a30
Revises: a8f4c2e91d10
Create Date: 2026-06-15 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c4e8f92a30"
down_revision: Union[str, None] = "a8f4c2e91d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("circuits", schema=None) as batch_op:
        batch_op.add_column(sa.Column("egress_country", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("egress_site_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("ipt_public_ip", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("ipt_nat_enabled", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.create_foreign_key(
            "fk_circuits_egress_site_id", "sites", ["egress_site_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("circuits", schema=None) as batch_op:
        batch_op.drop_constraint("fk_circuits_egress_site_id", type_="foreignkey")
        batch_op.drop_column("ipt_nat_enabled")
        batch_op.drop_column("ipt_public_ip")
        batch_op.drop_column("egress_site_id")
        batch_op.drop_column("egress_country")
