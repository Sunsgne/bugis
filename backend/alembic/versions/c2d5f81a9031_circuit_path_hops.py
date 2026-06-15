"""circuit path mode and transit hops

Revision ID: c2d5f81a9031
Revises: b1c4e8f92a30
Create Date: 2026-06-15 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d5f81a9031"
down_revision: Union[str, None] = "b1c4e8f92a30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("circuits", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("path_mode", sa.String(length=32), nullable=False, server_default="auto")
        )

    op.create_table(
        "circuit_path_hops",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("circuit_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["circuit_id"], ["circuits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("circuit_path_hops", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_circuit_path_hops_circuit_id"), ["circuit_id"])
        batch_op.create_index(batch_op.f("ix_circuit_path_hops_device_id"), ["device_id"])
        batch_op.create_index(batch_op.f("ix_circuit_path_hops_id"), ["id"])


def downgrade() -> None:
    op.drop_table("circuit_path_hops")
    with op.batch_alter_table("circuits", schema=None) as batch_op:
        batch_op.drop_column("path_mode")
