"""Add circuit availability events table."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e8f9a0b1c2d3"
down_revision = "d7e8f9a9050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "circuit_availability_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("circuit_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["circuit_id"], ["circuits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_circuit_availability_events_circuit_id"),
        "circuit_availability_events",
        ["circuit_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_circuit_availability_events_kind"),
        "circuit_availability_events",
        ["kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_circuit_availability_events_started_at"),
        "circuit_availability_events",
        ["started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_circuit_availability_events_started_at"), table_name="circuit_availability_events")
    op.drop_index(op.f("ix_circuit_availability_events_kind"), table_name="circuit_availability_events")
    op.drop_index(op.f("ix_circuit_availability_events_circuit_id"), table_name="circuit_availability_events")
    op.drop_table("circuit_availability_events")
