"""Retain work orders when circuits are deleted (audit trail).

Revision ID: u1v2w3x4455
Revises: t0u1v2w3344_alarm_templates
Create Date: 2026-06-19

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "u1v2w3x4455_wo_retention"
down_revision = "t0u1v2w3344_alarm_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "work_orders",
        sa.Column("circuit_code", sa.String(length=48), nullable=True),
    )
    op.execute(
        """
        UPDATE work_orders wo
        SET circuit_code = c.code
        FROM circuits c
        WHERE wo.circuit_id = c.id AND wo.circuit_code IS NULL
        """
    )
    with op.batch_alter_table("work_orders", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("work_orders_circuit_id_fkey"), type_="foreignkey"
        )
        batch_op.alter_column("circuit_id", existing_type=sa.Integer(), nullable=True)
        batch_op.create_foreign_key(
            "work_orders_circuit_id_fkey",
            "circuits",
            ["circuit_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            batch_op.f("ix_work_orders_circuit_code"), ["circuit_code"], unique=False
        )


def downgrade() -> None:
    op.execute("DELETE FROM work_orders WHERE circuit_id IS NULL")
    with op.batch_alter_table("work_orders", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_work_orders_circuit_code"))
        batch_op.drop_constraint(
            batch_op.f("work_orders_circuit_id_fkey"), type_="foreignkey"
        )
        batch_op.alter_column("circuit_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "work_orders_circuit_id_fkey",
            "circuits",
            ["circuit_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.drop_column("work_orders", "circuit_code")
