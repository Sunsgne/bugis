"""Normalize enum storage for path_mode and access_mode (SQLite demo fix).

Revision ID: e5f9b2c9041
Revises: d4e8a1b2c903
Create Date: 2026-06-15 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f9b2c9041"
down_revision: Union[str, None] = "d4e8a1b2c903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": name},
    ).first()
    return row is not None


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def upgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "circuits") and _column_exists(conn, "circuits", "path_mode"):
        conn.execute(
            sa.text(
                "UPDATE circuits SET path_mode = 'auto' "
                "WHERE path_mode IS NULL OR upper(path_mode) = 'AUTO'"
            )
        )
        conn.execute(
            sa.text(
                "UPDATE circuits SET path_mode = 'explicit_sr' "
                "WHERE upper(path_mode) = 'EXPLICIT_SR'"
            )
        )

    if _table_exists(conn, "circuit_endpoints") and _column_exists(
        conn, "circuit_endpoints", "access_mode"
    ):
        conn.execute(
            sa.text(
                "UPDATE circuit_endpoints SET access_mode = 'access' "
                "WHERE upper(access_mode) = 'ACCESS'"
            )
        )
        conn.execute(
            sa.text(
                "UPDATE circuit_endpoints SET access_mode = 'dot1q' "
                "WHERE upper(access_mode) = 'DOT1Q'"
            )
        )
        conn.execute(
            sa.text(
                "UPDATE circuit_endpoints SET access_mode = 'qinq' "
                "WHERE upper(access_mode) = 'QINQ'"
            )
        )


def downgrade() -> None:
    pass
