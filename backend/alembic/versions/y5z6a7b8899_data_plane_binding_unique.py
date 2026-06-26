"""Deduplicate data_plane_bindings and enforce one row per circuit/device/op."""
from __future__ import annotations

from alembic import op

revision = "y5z6a7b8899"
down_revision = "x4y5z6a7788"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM data_plane_bindings a
        USING data_plane_bindings b
        WHERE a.circuit_id = b.circuit_id
          AND a.device_id = b.device_id
          AND a.operation = b.operation
          AND a.id < b.id
        """
    )
    op.create_index(
        "uq_data_plane_binding",
        "data_plane_bindings",
        ["circuit_id", "device_id", "operation"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_data_plane_binding", table_name="data_plane_bindings")
