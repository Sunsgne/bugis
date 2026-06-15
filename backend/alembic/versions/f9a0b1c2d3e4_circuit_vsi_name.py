"""Add circuit.vsi_name for H3C VSI with uniqueness."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f9a0b1c2d3e4"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("circuits", schema=None) as batch_op:
        batch_op.add_column(sa.Column("vsi_name", sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f("ix_circuits_vsi_name"), ["vsi_name"], unique=True)

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, code FROM circuits WHERE code IS NOT NULL")).fetchall()
    used: set[str] = set()
    for row in rows:
        base = f"vsi_{str(row.code).replace('-', '_').lower()}"
        name = base
        n = 2
        while name in used:
            name = f"{base}_{n}"
            n += 1
        used.add(name)
        conn.execute(
            sa.text("UPDATE circuits SET vsi_name = :vsi WHERE id = :id"),
            {"vsi": name, "id": row.id},
        )


def downgrade() -> None:
    with op.batch_alter_table("circuits", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_circuits_vsi_name"))
        batch_op.drop_column("vsi_name")
