"""Authentication endpoints."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, is_tenant_user, require_admin
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.auth_challenge import AuthChallenge
from app.models.enums import MfaMethod, TenantStatus, UserScope
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import (
    LoginJsonRequest,
    LoginSecurityOut,
    MfaConfirmTotpRequest,
    MfaDisableRequest,
    MfaSendEmailRequest,
    MfaSetupTotpOut,
    MfaVerifyRequest,
    PasswordChangeRequest,
    StreamTicketOut,
    Token,
    UserCreate,
    UserOut,
)
from app.services import auth_security, email as email_svc, platform_settings as platform_cfg

router = APIRouter()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _load_user(db: Session, username: str) -> User | None:
    return db.execute(select(User).where(User.username == username)).scalar_one_or_none()


def _validate_tenant_user(db: Session, user: User) -> None:
    if not is_tenant_user(user):
        return
    if user.tenant_id is None:
        raise HTTPException(status_code=403, detail="门户账号未绑定租户")
    tenant = db.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=403, detail="租户不存在")
    if tenant.status != TenantStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="租户已暂停或终止")


def _issue_access_token(user: User) -> Token:
    return Token(access_token=create_access_token(subject=user.username))


def _begin_mfa(db: Session, user: User, plat) -> Token:
    methods = auth_security.available_mfa_methods(user, plat)
    if not methods:
        raise HTTPException(
            status_code=403,
            detail="已要求双因素认证，但账号未配置验证器或邮箱，请联系管理员",
        )
    mfa_token, _ = auth_security.create_challenge(
        db, purpose="mfa_login", user_id=user.id, ttl_seconds=300
    )
    return Token(
        mfa_required=True,
        mfa_token=mfa_token,
        mfa_methods=methods,
    )


def _authenticate_credentials(
    db: Session,
    *,
    username: str,
    password: str,
    ip_address: str,
    turnstile_token: str | None,
) -> User:
    plat = platform_cfg.get_or_create(db)
    auth_security.purge_expired_challenges(db)

    if auth_security.is_ip_rate_limited(db, plat, ip_address):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录尝试过于频繁，请稍后再试",
        )

    user = _load_user(db, username)
    need_captcha = auth_security.captcha_required(db, plat, ip_address, user)
    if need_captcha and not auth_security.verify_turnstile(plat, turnstile_token, ip_address):
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="需要完成人机验证",
        )

    if user and auth_security.user_is_locked(user):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="账号已临时锁定，请稍后再试",
        )

    if not user or not verify_password(password, user.hashed_password):
        auth_security.record_login_attempt(
            db, ip_address=ip_address, username=username, success=False
        )
        if user:
            auth_security.register_failed_login(db, user, plat)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="账号已停用")

    _validate_tenant_user(db, user)
    auth_security.record_login_attempt(
        db, ip_address=ip_address, username=username, success=True
    )
    auth_security.clear_failed_login(db, user)
    return user


@router.get("/login-security", response_model=LoginSecurityOut)
def login_security(db: Session = Depends(get_db)):
    plat = platform_cfg.get_or_create(db)
    return LoginSecurityOut(
        turnstile_enabled=plat.turnstile_enabled,
        turnstile_site_key=plat.turnstile_site_key or "",
        captcha_required_default=plat.turnstile_enabled,
    )


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    ip_address = _client_ip(request)
    user = _authenticate_credentials(
        db,
        username=form_data.username,
        password=form_data.password,
        ip_address=ip_address,
        turnstile_token=None,
    )
    plat = platform_cfg.get_or_create(db)
    if auth_security.mfa_required_for_user(user, plat):
        resp = _begin_mfa(db, user, plat)
        db.commit()
        return resp
    db.commit()
    return _issue_access_token(user)


@router.post("/login/json", response_model=Token)
def login_json(
    payload: LoginJsonRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    ip_address = _client_ip(request)
    plat = platform_cfg.get_or_create(db)

    user = _authenticate_credentials(
        db,
        username=payload.username,
        password=payload.password,
        ip_address=ip_address,
        turnstile_token=payload.turnstile_token,
    )
    if auth_security.mfa_required_for_user(user, plat):
        resp = _begin_mfa(db, user, plat)
        db.commit()
        return resp
    db.commit()
    return _issue_access_token(user)


@router.post("/mfa/verify", response_model=Token)
def mfa_verify(payload: MfaVerifyRequest, db: Session = Depends(get_db)):
    challenge = auth_security.consume_challenge(
        db, purpose="mfa_login", token=payload.mfa_token, code=None
    )
    if not challenge or not challenge.user_id:
        raise HTTPException(status_code=401, detail="MFA 会话已失效")
    user = db.get(User, challenge.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    ok = False
    if payload.method == "totp":
        secret = auth_security.decrypt_secret(user.totp_secret_encrypted)
        ok = bool(secret and auth_security.verify_totp(secret, payload.code))
    elif payload.method == "email":
        ok = bool(
            challenge.code_hash
            and auth_security.hash_code(payload.code) == challenge.code_hash
        )
    if not ok:
        raise HTTPException(status_code=401, detail="验证码错误")

    challenge.consumed_at = challenge.consumed_at or challenge.created_at
    db.add(challenge)
    db.commit()
    return _issue_access_token(user)


@router.post("/mfa/send-email")
def mfa_send_email(payload: MfaSendEmailRequest, db: Session = Depends(get_db)):
    challenge = db.execute(
        select(AuthChallenge).where(
            AuthChallenge.purpose == "mfa_login",
            AuthChallenge.token_hash == auth_security.hash_token(payload.mfa_token),
            AuthChallenge.consumed_at.is_(None),
        )
    ).scalar_one_or_none()
    if not challenge or not challenge.user_id:
        raise HTTPException(status_code=401, detail="MFA 会话已失效")
    user = db.get(User, challenge.user_id)
    if not user or not user.email:
        raise HTTPException(status_code=400, detail="账号未配置邮箱")

    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge.code_hash = auth_security.hash_code(code)
    db.add(challenge)
    plat = platform_cfg.get_or_create(db)
    ok, detail = email_svc.send_email(
        db,
        to=user.email,
        subject=f"{plat.product_name} 登录验证码",
        body=f"您的登录验证码为 {code}，5 分钟内有效。如非本人操作请忽略。",
    )
    db.commit()
    if not ok:
        raise HTTPException(status_code=503, detail=f"邮件发送失败: {detail}")
    return {"sent": True}


@router.get("/mfa/totp/setup", response_model=MfaSetupTotpOut)
def mfa_setup_totp(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plat = platform_cfg.get_or_create(db)
    if not plat.mfa_allow_totp:
        raise HTTPException(status_code=400, detail="平台未启用验证器 MFA")
    secret = auth_security.new_totp_secret()
    user.totp_secret_encrypted = auth_security.encrypt_secret(secret)
    user.mfa_method = MfaMethod.TOTP
    db.add(user)
    db.commit()
    return MfaSetupTotpOut(
        secret=secret,
        provisioning_uri=auth_security.totp_provisioning_uri(
            secret, username=user.username, issuer=plat.product_name
        ),
    )


@router.post("/mfa/totp/confirm", response_model=UserOut)
def mfa_confirm_totp(
    payload: MfaConfirmTotpRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    secret = auth_security.decrypt_secret(user.totp_secret_encrypted)
    if not secret or not auth_security.verify_totp(secret, payload.code):
        raise HTTPException(status_code=400, detail="验证码错误")
    user.mfa_enabled = True
    user.mfa_method = MfaMethod.TOTP
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/mfa/disable", response_model=UserOut)
def mfa_disable(
    payload: MfaDisableRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="密码不正确")
    secret = auth_security.decrypt_secret(user.totp_secret_encrypted)
    ok = bool(secret and auth_security.verify_totp(secret, payload.code))
    if not ok:
        raise HTTPException(status_code=400, detail="验证码错误")
    user.mfa_enabled = False
    user.mfa_method = MfaMethod.NONE
    user.totp_secret_encrypted = None
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/stream/ticket", response_model=StreamTicketOut)
def create_stream_ticket(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket, _ = auth_security.create_challenge(
        db, purpose="sse", user_id=user.id, ttl_seconds=60
    )
    db.commit()
    return StreamTicketOut(ticket=ticket, expires_in=60)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password", status_code=204)
def change_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="新密码至少 8 位")
    user.hashed_password = hash_password(payload.new_password)
    db.add(user)
    db.commit()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    exists = db.execute(
        select(User).where(User.username == payload.username)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="username already exists")
    user = User(
        username=payload.username,
        full_name=payload.full_name,
        email=payload.email,
        role=payload.role,
        scope=UserScope.PLATFORM,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.execute(select(User)).scalars().all()
