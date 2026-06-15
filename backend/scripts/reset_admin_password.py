"""Reset a platform user's password (e.g. after deploy).

Usage:
  python -m scripts.reset_admin_password admin 'NewStrongPassword'
"""
from __future__ import annotations

import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.reset_admin_password <username> <password>", file=sys.stderr)
        raise SystemExit(2)
    username, password = sys.argv[1], sys.argv[2]
    if len(password) < 8:
        print("Password must be at least 8 characters", file=sys.stderr)
        raise SystemExit(1)

    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if not user:
            print(f"User not found: {username}", file=sys.stderr)
            raise SystemExit(1)
        user.hashed_password = hash_password(password)
        db.commit()
        print(f"Password updated for {username}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
