"""Password hashing and JWT token helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode(),
            hashed_password.encode(),
        )
    except ValueError:
        return False


def create_access_token(subject: str | Any, expires_minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    to_encode = {"exp": expire, "sub": str(subject), "typ": "access"}
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_pre_auth_token(subject: str | Any, expires_minutes: int = 5) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes
    )
    to_encode = {"exp": expire, "sub": str(subject), "typ": "preauth"}
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_pre_auth_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        if payload.get("typ") != "preauth":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        if payload.get("typ") not in (None, "access"):
            return None
        return payload.get("sub")
    except JWTError:
        return None
