"""Convert PostgreSQL native enum columns to VARCHAR for str-enum ORM parity.

Revision ID: f6a7b8c9042
Revises: e5f9b2c9041
Create Date: 2026-06-15 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9042"
down_revision: Union[str, None] = "e5f9b2c9041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    rows = conn.execute(
        sa.text(
            """
            SELECT c.table_name, c.column_name
            FROM information_schema.columns c
            JOIN pg_type t ON c.udt_name = t.typname
            WHERE c.table_schema = 'public'
              AND EXISTS (SELECT 1 FROM pg_enum e WHERE e.enumtypid = t.oid)
            GROUP BY c.table_name, c.column_name
            ORDER BY c.table_name, c.column_name
            """
        )
    ).all()

    for table_name, column_name in rows:
        conn.execute(
            sa.text(
                f'ALTER TABLE "{table_name}" '
                f'ALTER COLUMN "{column_name}" TYPE VARCHAR(64) '
                f'USING "{column_name}"::text'
            )
        )

    enum_names = conn.execute(
        sa.text(
            """
            SELECT DISTINCT t.typname
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            """
        )
    ).scalars().all()
    for enum_name in enum_names:
        conn.execute(sa.text(f'DROP TYPE IF EXISTS "{enum_name}"'))


def downgrade() -> None:
    pass
