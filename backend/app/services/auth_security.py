"""Security helpers: encryption, challenge tokens, Turnstile verification."""
from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import httpx
import pyotp
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth_challenge import AuthChallenge
from app.models.login_attempt import LoginAttempt
from app.models.platform_settings import PlatformSettings
from app.models.user import User


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.secret_key.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode()).hexdigest()


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, *, username: str, issuer: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code.strip(), valid_window=1)


def create_challenge(
    db: Session,
    *,
    purpose: str,
    user_id: int | None,
    ttl_seconds: int,
    code: str | None = None,
) -> tuple[str, AuthChallenge]:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    row = AuthChallenge(
        user_id=user_id,
        purpose=purpose,
        token_hash=hash_token(token),
        code_hash=hash_code(code) if code else None,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    db.add(row)
    db.flush()
    return token, row


def consume_challenge(
    db: Session,
    *,
    purpose: str,
    token: str,
    code: str | None = None,
) -> AuthChallenge | None:
    row = validate_challenge(db, purpose=purpose, token=token)
    if not row:
        return None
    if code is not None:
        if not row.code_hash or row.code_hash != hash_code(code):
            return None
    row.consumed_at = datetime.now(timezone.utc)
    db.add(row)
    return row


def find_user_challenge(
    db: Session,
    *,
    purpose: str,
    user_id: int,
) -> AuthChallenge | None:
    """Return the most recent unconsumed, unexpired challenge for a user.

    Used for code-based flows (e.g. password reset) where the caller is
    identified by username/e-mail rather than an opaque challenge token.
    """
    now = datetime.now(timezone.utc)
    return db.execute(
        select(AuthChallenge)
        .where(
            AuthChallenge.purpose == purpose,
            AuthChallenge.user_id == user_id,
            AuthChallenge.consumed_at.is_(None),
            AuthChallenge.expires_at > now,
        )
        .order_by(AuthChallenge.id.desc())
    ).scalars().first()


def validate_challenge(
    db: Session,
    *,
    purpose: str,
    token: str,
) -> AuthChallenge | None:
    now = datetime.now(timezone.utc)
    return db.execute(
        select(AuthChallenge).where(
            AuthChallenge.purpose == purpose,
            AuthChallenge.token_hash == hash_token(token),
            AuthChallenge.consumed_at.is_(None),
            AuthChallenge.expires_at > now,
        )
    ).scalar_one_or_none()


def purge_expired_challenges(db: Session) -> None:
    now = datetime.now(timezone.utc)
    db.execute(delete(AuthChallenge).where(AuthChallenge.expires_at <= now))


def record_login_attempt(
    db: Session, *, ip_address: str, username: str | None, success: bool
) -> None:
    db.add(
        LoginAttempt(
            ip_address=ip_address,
            username=username,
            success=success,
        )
    )


def count_recent_failures(
    db: Session, *, ip_address: str, window_minutes: int
) -> int:
    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    return (
        db.scalar(
            select(func.count(LoginAttempt.id)).where(
                LoginAttempt.ip_address == ip_address,
                LoginAttempt.success.is_(False),
                LoginAttempt.created_at >= since,
            )
        )
        or 0
    )


def is_ip_rate_limited(db: Session, plat: PlatformSettings, ip_address: str) -> bool:
    failures = count_recent_failures(
        db, ip_address=ip_address, window_minutes=plat.login_rate_limit_window_minutes
    )
    return failures >= plat.login_rate_limit_per_ip


def user_is_locked(user: User) -> bool:
    if not user.locked_until:
        return False
    locked_until = user.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) < locked_until


def register_failed_login(db: Session, user: User | None, plat: PlatformSettings) -> None:
    if not user:
        return
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= plat.login_lockout_after_failures:
        user.locked_until = datetime.now(timezone.utc) + timedelta(
            minutes=plat.login_lockout_minutes
        )
    db.add(user)


def clear_failed_login(db: Session, user: User) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)


def captcha_required(
    db: Session, plat: PlatformSettings, ip_address: str, user: User | None
) -> bool:
    if plat.turnstile_enabled:
        return True
    threshold = plat.captcha_after_failures or 0
    if threshold <= 0:
        return False
    ip_failures = count_recent_failures(
        db, ip_address=ip_address, window_minutes=plat.login_rate_limit_window_minutes
    )
    if ip_failures >= threshold:
        return True
    if user and (user.failed_login_attempts or 0) >= threshold:
        return True
    return False


def verify_turnstile(plat: PlatformSettings, token: str | None, ip_address: str) -> bool:
    if not plat.turnstile_enabled:
        return True
    secret = plat.turnstile_secret_key or ""
    if not secret or not token:
        return False
    if settings.dry_run and token == "dry-run-turnstile":
        return True
    try:
        resp = httpx.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": secret, "response": token, "remoteip": ip_address},
            timeout=8,
        )
        data = resp.json()
        return bool(data.get("success"))
    except Exception:
        return False


def mfa_required_for_user(user: User, plat: PlatformSettings) -> bool:
    if user.mfa_enabled:
        return True
    from app.models.enums import UserScope

    if user.scope == UserScope.TENANT:
        return plat.mfa_required_portal
    return plat.mfa_required_platform


def available_mfa_methods(user: User, plat: PlatformSettings) -> list[str]:
    methods: list[str] = []
    if plat.mfa_allow_totp and user.totp_secret_encrypted:
        methods.append("totp")
    if plat.mfa_allow_email and user.email:
        methods.append("email")
    if not methods and user.mfa_enabled:
        if plat.mfa_allow_totp:
            methods.append("totp")
        if plat.mfa_allow_email and user.email:
            methods.append("email")
    return methods
