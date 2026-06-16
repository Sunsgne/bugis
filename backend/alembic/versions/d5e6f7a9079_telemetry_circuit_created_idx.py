"""Add telemetry_samples (circuit_id, created_at) index for range queries."""
from __future__ import annotations

from alembic import op

revision = "d5e6f7a9079_telemetry_idx"
down_revision = "b2c3d4e9055_prod_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_telemetry_samples_circuit_created",
        "telemetry_samples",
        ["circuit_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_telemetry_samples_circuit_created", table_name="telemetry_samples")
