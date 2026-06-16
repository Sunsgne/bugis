"""Merge tenant portal and device mgmt failover branches."""
from __future__ import annotations

from alembic import op

revision = "f6a7b8c9081_merge_heads"
down_revision = ("d5e6f7a9077_device_mgmt_failover", "e6f7a8b9080_tenant_portal")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
