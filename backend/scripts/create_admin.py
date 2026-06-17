"""Create (or promote) a platform administrator account.

Designed to be run against a live deployment (e.g. production) without
hardcoding any credentials in the repository. Credentials are passed at
runtime as arguments or environment variables.

Usage:
  python -m scripts.create_admin <username> <password> [--full-name NAME] [--email EMAIL]
  python -m scripts.create_admin <username> --password-env BUGIS_NEW_ADMIN_PASS

Behaviour:
  * If the user does not exist, a new active PLATFORM/ADMIN account is created.
  * If the user already exists, the command refuses to overwrite it unless
    --update is given; with --update it resets the password and ensures the
    account is an active platform administrator.

Examples:
  # Local / SQLite
  cd backend && python -m scripts.create_admin <username> '<password>'

  # Production (Docker Compose)
  docker compose -f docker-compose.prod.yml exec backend \
      python -m scripts.create_admin <username> '<password>'
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.enums import UserRole, UserScope  # noqa: E402
from app.models.user import User  # noqa: E402

MIN_PASSWORD_LENGTH = 8


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="scripts.create_admin",
        description="Create or promote a platform administrator account.",
    )
    parser.add_argument("username", help="Login username for the administrator")
    parser.add_argument(
        "password",
        nargs="?",
        default=None,
        help="Password (omit and use --password-env to avoid shell history)",
    )
    parser.add_argument(
        "--password-env",
        default=None,
        help="Read the password from this environment variable instead of the CLI arg",
    )
    parser.add_argument("--full-name", default=None, help="Display name")
    parser.add_argument("--email", default=None, help="Contact email")
    parser.add_argument(
        "--update",
        action="store_true",
        help="If the user already exists, reset its password and ensure admin rights",
    )
    return parser.parse_args(argv)


def _resolve_password(args: argparse.Namespace) -> str:
    if args.password_env:
        password = os.environ.get(args.password_env)
        if not password:
            print(
                f"Environment variable {args.password_env} is empty or unset",
                file=sys.stderr,
            )
            raise SystemExit(2)
        return password
    if args.password:
        return args.password
    print(
        "A password is required (positional argument or --password-env)",
        file=sys.stderr,
    )
    raise SystemExit(2)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    password = _resolve_password(args)
    if len(password) < MIN_PASSWORD_LENGTH:
        print(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters",
            file=sys.stderr,
        )
        raise SystemExit(1)

    db = SessionLocal()
    try:
        existing = db.execute(
            select(User).where(User.username == args.username)
        ).scalar_one_or_none()

        if existing:
            if not args.update:
                print(
                    f"User already exists: {args.username} "
                    "(pass --update to reset password and promote to admin)",
                    file=sys.stderr,
                )
                raise SystemExit(1)
            existing.hashed_password = hash_password(password)
            existing.role = UserRole.ADMIN
            existing.scope = UserScope.PLATFORM
            existing.tenant_id = None
            existing.is_active = True
            if args.full_name is not None:
                existing.full_name = args.full_name
            if args.email is not None:
                existing.email = args.email
            db.add(existing)
            db.commit()
            print(f"Updated existing user to platform admin: {args.username}")
            return

        user = User(
            username=args.username,
            full_name=args.full_name or "Platform Administrator",
            email=args.email,
            role=UserRole.ADMIN,
            scope=UserScope.PLATFORM,
            hashed_password=hash_password(password),
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Created platform admin: {args.username}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
