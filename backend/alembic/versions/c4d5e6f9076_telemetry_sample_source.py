"""Add telemetry sample source provenance."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c4d5e6f9076_telemetry_source"
down_revision = "c4d5e6f9078_iface_desc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "telemetry_samples",
        sa.Column("source", sa.String(length=32), nullable=True, server_default="unknown"),
    )
    op.execute("UPDATE telemetry_samples SET source = 'legacy' WHERE source IS NULL OR source = 'unknown'")


def downgrade() -> None:
    op.drop_column("telemetry_samples", "source")
