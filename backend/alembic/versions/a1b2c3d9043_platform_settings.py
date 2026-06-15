"""Platform settings singleton table."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d9043"
down_revision = "f3a2b1c9042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("netconf_timeout", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("baseline_ntp_server", sa.String(length=64), nullable=False, server_default="10.0.0.1"),
        sa.Column("baseline_syslog_server", sa.String(length=64), nullable=False, server_default="10.0.0.2"),
        sa.Column("scheduler_enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("scheduler_interval_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("threshold_packet_loss_pct", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("threshold_latency_ms", sa.Float(), nullable=False, server_default="50"),
        sa.Column("threshold_utilization_pct", sa.Float(), nullable=False, server_default="90"),
        sa.Column("threshold_health_score", sa.Float(), nullable=False, server_default="70"),
        sa.Column("threshold_link_utilization_pct", sa.Float(), nullable=False, server_default="85"),
        sa.Column("controller_bgp_asn", sa.Integer(), nullable=False, server_default="65000"),
        sa.Column("controller_node_id", sa.String(length=64), nullable=False, server_default="bugis-1"),
        sa.Column("webhook_token", sa.String(length=128), nullable=False, server_default="bugis-webhook-token"),
        sa.Column("smtp_host", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("smtp_user", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("smtp_password", sa.String(length=255), nullable=True),
        sa.Column("smtp_from", sa.String(length=255), nullable=False, server_default="bugis@localhost"),
        sa.Column("enable_metrics", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("access_token_expire_minutes", sa.Integer(), nullable=False, server_default="1440"),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("platform_settings")
