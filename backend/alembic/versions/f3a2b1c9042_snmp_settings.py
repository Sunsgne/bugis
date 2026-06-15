"""Global SNMP settings table."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f3a2b1c9042"
down_revision = "e5f9b2c9041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "snmp_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("version", sa.String(length=8), nullable=False, server_default="2c"),
        sa.Column("community", sa.String(length=128), nullable=False, server_default="bugis-ro"),
        sa.Column("write_community", sa.String(length=128), nullable=True),
        sa.Column("port", sa.Integer(), nullable=False, server_default="161"),
        sa.Column("timeout_sec", sa.Float(), nullable=False, server_default="2"),
        sa.Column("retries", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_repetitions", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("prefer_device_community", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("walk_if_descr", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("walk_if_alias", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("walk_if_high_speed", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("walk_if_oper_status", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("sync_link_capacity", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("auto_discover_on_check", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("exclude_name_patterns", sa.JSON(), nullable=True),
        sa.Column("include_name_patterns", sa.JSON(), nullable=True),
        sa.Column("v3_username", sa.String(length=64), nullable=True),
        sa.Column("v3_security_level", sa.String(length=16), nullable=False, server_default="authPriv"),
        sa.Column("v3_auth_protocol", sa.String(length=16), nullable=True),
        sa.Column("v3_auth_password", sa.String(length=255), nullable=True),
        sa.Column("v3_priv_protocol", sa.String(length=16), nullable=True),
        sa.Column("v3_priv_password", sa.String(length=255), nullable=True),
        sa.Column("v3_context_name", sa.String(length=64), nullable=True),
        sa.Column("baseline_community", sa.String(length=128), nullable=False, server_default="bugis-ro"),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("snmp_settings")
