"""Backfill endpoint vlan_id from circuit-level Service VLAN."""
from __future__ import annotations

from alembic import op

revision = "a7b8c9d0011"
down_revision = "z6a7b8c9900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE circuit_endpoints AS ce
        SET vlan_id = c.vlan_id
        FROM circuits AS c
        WHERE ce.circuit_id = c.id
          AND ce.vlan_id IS NULL
          AND c.vlan_id IS NOT NULL
          AND ce.access_mode <> 'access'
        """
    )


def downgrade() -> None:
    pass
