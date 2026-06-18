"""Widen credential columns for Fernet-encrypted values at rest."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "k1l2m3n4400_encrypt_cred_columns"
down_revision = "j0k1l2m3300_prov_concurrency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.alter_column(
            "snmp_community",
            existing_type=sa.String(length=64),
            type_=sa.String(length=512),
            existing_nullable=True,
        )
    with op.batch_alter_table("snmp_settings", schema=None) as batch_op:
        batch_op.alter_column(
            "community",
            existing_type=sa.String(length=128),
            type_=sa.String(length=512),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "write_community",
            existing_type=sa.String(length=128),
            type_=sa.String(length=512),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "baseline_community",
            existing_type=sa.String(length=128),
            type_=sa.String(length=512),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("snmp_settings", schema=None) as batch_op:
        batch_op.alter_column(
            "baseline_community",
            existing_type=sa.String(length=512),
            type_=sa.String(length=128),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "write_community",
            existing_type=sa.String(length=512),
            type_=sa.String(length=128),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "community",
            existing_type=sa.String(length=512),
            type_=sa.String(length=128),
            existing_nullable=False,
        )
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.alter_column(
            "snmp_community",
            existing_type=sa.String(length=512),
            type_=sa.String(length=64),
            existing_nullable=True,
        )
