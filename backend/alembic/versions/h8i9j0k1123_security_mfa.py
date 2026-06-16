"""Platform security & MFA settings (singleton row extensions)."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "h8i9j0k1123_security_mfa"
down_revision = "g7h8i9j9102_auto_learn_adopted"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("mfa_method", sa.String(length=16), nullable=False, server_default="none")
        )
        batch_op.add_column(sa.Column("totp_secret_encrypted", sa.String(length=512), nullable=True))
        batch_op.add_column(
            sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("platform_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("login_rate_limit_per_ip", sa.Integer(), nullable=False, server_default="30")
        )
        batch_op.add_column(
            sa.Column(
                "login_rate_limit_window_minutes",
                sa.Integer(),
                nullable=False,
                server_default="15",
            )
        )
        batch_op.add_column(
            sa.Column(
                "login_lockout_after_failures",
                sa.Integer(),
                nullable=False,
                server_default="5",
            )
        )
        batch_op.add_column(
            sa.Column("login_lockout_minutes", sa.Integer(), nullable=False, server_default="15")
        )
        batch_op.add_column(
            sa.Column("captcha_after_failures", sa.Integer(), nullable=False, server_default="3")
        )
        batch_op.add_column(
            sa.Column("turnstile_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("turnstile_site_key", sa.String(length=128), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("turnstile_secret_key", sa.String(length=256), nullable=True))
        batch_op.add_column(
            sa.Column(
                "mfa_required_platform", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch_op.add_column(
            sa.Column("mfa_required_portal", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("mfa_allow_totp", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column("mfa_allow_email", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column("expose_openapi", sa.Boolean(), nullable=False, server_default=sa.true())
        )

    op.create_table(
        "auth_challenges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_auth_challenges_purpose", "auth_challenges", ["purpose"])
    op.create_index("ix_auth_challenges_user_id", "auth_challenges", ["user_id"])
    op.create_index("ix_auth_challenges_expires_at", "auth_challenges", ["expires_at"])

    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_login_attempts_ip_address", "login_attempts", ["ip_address"])
    op.create_index("ix_login_attempts_username", "login_attempts", ["username"])


def downgrade() -> None:
    op.drop_index("ix_login_attempts_username", table_name="login_attempts")
    op.drop_index("ix_login_attempts_ip_address", table_name="login_attempts")
    op.drop_table("login_attempts")
    op.drop_index("ix_auth_challenges_expires_at", table_name="auth_challenges")
    op.drop_index("ix_auth_challenges_user_id", table_name="auth_challenges")
    op.drop_index("ix_auth_challenges_purpose", table_name="auth_challenges")
    op.drop_table("auth_challenges")

    with op.batch_alter_table("platform_settings", schema=None) as batch_op:
        for col in (
            "expose_openapi",
            "mfa_allow_email",
            "mfa_allow_totp",
            "mfa_required_portal",
            "mfa_required_platform",
            "turnstile_secret_key",
            "turnstile_site_key",
            "turnstile_enabled",
            "captcha_after_failures",
            "login_lockout_minutes",
            "login_lockout_after_failures",
            "login_rate_limit_window_minutes",
            "login_rate_limit_per_ip",
        ):
            batch_op.drop_column(col)

    with op.batch_alter_table("users", schema=None) as batch_op:
        for col in (
            "last_login_at",
            "locked_until",
            "failed_login_attempts",
            "totp_secret_encrypted",
            "mfa_method",
            "mfa_enabled",
        ):
            batch_op.drop_column(col)
