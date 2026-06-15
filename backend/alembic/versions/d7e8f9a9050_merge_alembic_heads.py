"""Merge Alembic heads (device SNMP fields + PostgreSQL varchar enums).

Revision ID: d7e8f9a9050
Revises: a5b6c7d9087, f6a7b8c9042
Create Date: 2026-06-15 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d7e8f9a9050"
down_revision: Union[str, tuple[str, ...], None] = ("a5b6c7d9087", "f6a7b8c9042")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
