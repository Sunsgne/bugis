"""Telemetry time-series indexes for circuit charts and billing.

Production baseline (2026-06): ~3k rows — composite B-tree indexes are sufficient.
Revisit monthly RANGE partitioning when telemetry_samples exceeds ~500k rows
(~90 days at 20 circuits × 3 samples/min) or billing queries exceed 200ms.

Indexes match:
  - list_circuit_samples: circuit_id + created_at DESC [+ source]
  - overview_traffic: created_at range scan
  - billing_95th: circuit_id + month window on created_at
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "o5p6q7r8800_telemetry_idx"
down_revision = "n4o5p6q7700_latency_probe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Replaced by composite (circuit_id, created_at DESC).
    op.drop_index("ix_telemetry_samples_circuit_id", table_name="telemetry_samples")

    op.create_index(
        "ix_ts_circuit_created",
        "telemetry_samples",
        ["circuit_id", "created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "ix_ts_circuit_source_created",
        "telemetry_samples",
        ["circuit_id", "source", "created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "ix_ts_created_id",
        "telemetry_samples",
        ["created_at", "id"],
        unique=False,
        postgresql_ops={"created_at": "DESC", "id": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("ix_ts_created_id", table_name="telemetry_samples")
    op.drop_index("ix_ts_circuit_source_created", table_name="telemetry_samples")
    op.drop_index("ix_ts_circuit_created", table_name="telemetry_samples")
    op.create_index(
        "ix_telemetry_samples_circuit_id",
        "telemetry_samples",
        ["circuit_id"],
        unique=False,
    )
