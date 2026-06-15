"""device interface S-VID inventory column

Revision ID: d4e8a1b2c903
Revises: c2d5f81a9031
Create Date: 2026-06-15 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e8a1b2c903"
down_revision: Union[str, None] = "c2d5f81a9031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("device_interfaces", schema=None) as batch_op:
        batch_op.add_column(sa.Column("used_s_vids", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("device_interfaces", schema=None) as batch_op:
        batch_op.drop_column("used_s_vids")
