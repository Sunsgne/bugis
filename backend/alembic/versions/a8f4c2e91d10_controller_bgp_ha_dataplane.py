"""controller bgp sessions, cluster HA, data-plane bindings, route encap

Revision ID: a8f4c2e91d10
Revises: 32a1f53e5bb0
Create Date: 2026-06-15 09:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8f4c2e91d10"
down_revision: Union[str, None] = "32a1f53e5bb0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("evpn_routes", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "encap",
                sa.Enum("VXLAN", "MPLS", name="evpnencap"),
                nullable=False,
                server_default="VXLAN",
            )
        )
        batch_op.add_column(sa.Column("mpls_label", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("sr_sid", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_evpn_routes_encap"), ["encap"], unique=False)

    op.create_table(
        "bgp_evpn_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("device_name", sa.String(length=128), nullable=False),
        sa.Column("peer_ip", sa.String(length=64), nullable=False),
        sa.Column("local_asn", sa.Integer(), nullable=False),
        sa.Column("remote_asn", sa.Integer(), nullable=True),
        sa.Column(
            "state",
            sa.Enum("IDLE", "CONNECT", "ESTABLISHED", name="bgpsessionstate"),
            nullable=False,
        ),
        sa.Column("routes_received", sa.Integer(), nullable=False),
        sa.Column("routes_sent", sa.Integer(), nullable=False),
        sa.Column("last_keepalive", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config_snippet", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("bgp_evpn_sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_bgp_evpn_sessions_device_id"), ["device_id"], unique=True)
        batch_op.create_index(batch_op.f("ix_bgp_evpn_sessions_id"), ["id"], unique=False)
        batch_op.create_index(batch_op.f("ix_bgp_evpn_sessions_peer_ip"), ["peer_ip"], unique=False)
        batch_op.create_index(batch_op.f("ix_bgp_evpn_sessions_state"), ["state"], unique=False)

    op.create_table(
        "controller_cluster_nodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.String(length=64), nullable=False),
        sa.Column("hostname", sa.String(length=128), nullable=False),
        sa.Column(
            "role",
            sa.Enum("LEADER", "STANDBY", "CANDIDATE", name="controllernoderole"),
            nullable=False,
        ),
        sa.Column("api_url", sa.String(length=255), nullable=False),
        sa.Column("rib_version", sa.Integer(), nullable=False),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_local", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("controller_cluster_nodes", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_controller_cluster_nodes_id"), ["id"], unique=False)
        batch_op.create_index(batch_op.f("ix_controller_cluster_nodes_node_id"), ["node_id"], unique=True)
        batch_op.create_index(batch_op.f("ix_controller_cluster_nodes_role"), ["role"], unique=False)

    op.create_table(
        "data_plane_bindings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("circuit_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=True),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column("transport", sa.String(length=32), nullable=False),
        sa.Column(
            "state",
            sa.Enum("PENDING", "RENDERED", "APPLIED", "FAILED", name="dataplanestate"),
            nullable=False,
        ),
        sa.Column("config_preview", sa.Text(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["circuit_id"], ["circuits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("data_plane_bindings", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_data_plane_bindings_circuit_id"), ["circuit_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_data_plane_bindings_device_id"), ["device_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_data_plane_bindings_id"), ["id"], unique=False)
        batch_op.create_index(batch_op.f("ix_data_plane_bindings_state"), ["state"], unique=False)
        batch_op.create_index(batch_op.f("ix_data_plane_bindings_work_order_id"), ["work_order_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("data_plane_bindings", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_data_plane_bindings_work_order_id"))
        batch_op.drop_index(batch_op.f("ix_data_plane_bindings_state"))
        batch_op.drop_index(batch_op.f("ix_data_plane_bindings_id"))
        batch_op.drop_index(batch_op.f("ix_data_plane_bindings_device_id"))
        batch_op.drop_index(batch_op.f("ix_data_plane_bindings_circuit_id"))
    op.drop_table("data_plane_bindings")

    with op.batch_alter_table("controller_cluster_nodes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_controller_cluster_nodes_role"))
        batch_op.drop_index(batch_op.f("ix_controller_cluster_nodes_node_id"))
        batch_op.drop_index(batch_op.f("ix_controller_cluster_nodes_id"))
    op.drop_table("controller_cluster_nodes")

    with op.batch_alter_table("bgp_evpn_sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_bgp_evpn_sessions_state"))
        batch_op.drop_index(batch_op.f("ix_bgp_evpn_sessions_peer_ip"))
        batch_op.drop_index(batch_op.f("ix_bgp_evpn_sessions_id"))
        batch_op.drop_index(batch_op.f("ix_bgp_evpn_sessions_device_id"))
    op.drop_table("bgp_evpn_sessions")

    with op.batch_alter_table("evpn_routes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_evpn_routes_encap"))
        batch_op.drop_column("sr_sid")
        batch_op.drop_column("mpls_label")
        batch_op.drop_column("encap")
