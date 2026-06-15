"""Device management transport + platform southbound defaults."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d9044_mgmt_ifaces"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "platform_settings",
        sa.Column("ssh_timeout", sa.Integer(), nullable=False, server_default="30"),
    )
    op.add_column(
        "platform_settings",
        sa.Column("default_netconf_port", sa.Integer(), nullable=False, server_default="830"),
    )
    op.add_column(
        "platform_settings",
        sa.Column("default_ssh_port", sa.Integer(), nullable=False, server_default="22"),
    )
    op.add_column(
        "platform_settings",
        sa.Column("default_username", sa.String(length=64), nullable=False, server_default="admin"),
    )

    op.add_column(
        "devices",
        sa.Column(
            "management_transport",
            sa.String(length=16),
            nullable=False,
            server_default="auto",
        ),
    )
    op.add_column("devices", sa.Column("enable_password", sa.String(length=255), nullable=True))
    op.add_column("devices", sa.Column("netmiko_device_type", sa.String(length=64), nullable=True))
    op.add_column("devices", sa.Column("snmp_v3_username", sa.String(length=64), nullable=True))
    op.add_column("devices", sa.Column("snmp_v3_auth_password", sa.String(length=255), nullable=True))
    op.add_column("devices", sa.Column("snmp_v3_priv_password", sa.String(length=255), nullable=True))
    op.add_column("devices", sa.Column("snmp_v3_security_level", sa.String(length=16), nullable=True))
    op.add_column("devices", sa.Column("snmp_v3_auth_protocol", sa.String(length=16), nullable=True))
    op.add_column("devices", sa.Column("snmp_v3_priv_protocol", sa.String(length=16), nullable=True))


def downgrade() -> None:
    for col in (
        "snmp_v3_priv_protocol",
        "snmp_v3_auth_protocol",
        "snmp_v3_security_level",
        "snmp_v3_priv_password",
        "snmp_v3_auth_password",
        "snmp_v3_username",
        "netmiko_device_type",
        "enable_password",
        "management_transport",
    ):
        op.drop_column("devices", col)
    for col in ("default_username", "default_ssh_port", "default_netconf_port", "ssh_timeout"):
        op.drop_column("platform_settings", col)
