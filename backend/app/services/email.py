"""Transactional email helper (MFA codes, security notifications)."""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services import email_templates, platform_settings as platform_cfg


def send_email(
    db: Session,
    *,
    to: str,
    subject: str,
    body: str,
    html: str | None = None,
) -> tuple[bool, str]:
    """Send an e-mail. When *html* is provided a multipart/alternative message
    is sent (HTML + plain-text fallback); otherwise a plain-text message."""
    plat = platform_cfg.get_or_create(db)
    host = plat.smtp_host or settings.smtp_host
    if not host:
        return False, "SMTP 未配置"
    port = int(plat.smtp_port or settings.smtp_port or 25)
    security = (plat.smtp_security or settings.smtp_security or "starttls").lower()
    user = plat.smtp_user or settings.smtp_user or ""
    password = plat.smtp_password or settings.smtp_password or ""
    sender = plat.smtp_from or settings.smtp_from or "bugis@localhost"
    if settings.dry_run:
        return True, f"[DRY-RUN] email -> {to}"

    if html:
        msg: MIMEText | MIMEMultipart = MIMEMultipart("alternative")
        msg.attach(MIMEText(body, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
    else:
        msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    try:
        if security == "ssl":
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
        with server as s:
            if security == "starttls":
                s.starttls()
            if user:
                s.login(user, password)
            s.send_message(msg)
        return True, "sent"
    except Exception as exc:
        return False, f"smtp error: {exc}"


def send_mfa_code_email(
    db: Session, *, to: str, code: str, ttl_minutes: int = 5
) -> tuple[bool, str]:
    plat = platform_cfg.get_or_create(db)
    product = plat.product_name or "Network Ops"
    html = email_templates.render_email(
        plat,
        heading="登录验证码",
        intro="您正在登录账号，请在登录页面输入下方验证码以完成双因素身份验证。",
        code=code,
        code_caption="登录验证码",
        outro=f"验证码 {ttl_minutes} 分钟内有效，请勿向任何人泄露。",
        note="若这不是您本人的操作，您的密码可能已泄露，建议尽快修改密码并启用验证器 (TOTP)。",
    )
    body = (
        f"【{product}】登录验证码：{code}\n"
        f"{ttl_minutes} 分钟内有效，请勿泄露。如非本人操作请忽略。"
    )
    return send_email(
        db,
        to=to,
        subject=f"{product} · 登录验证码 {code}",
        body=body,
        html=html,
    )


def send_password_reset_email(
    db: Session, *, to: str, code: str, ttl_minutes: int = 15
) -> tuple[bool, str]:
    plat = platform_cfg.get_or_create(db)
    product = plat.product_name or "Network Ops"
    html = email_templates.render_email(
        plat,
        heading="重置登录密码",
        intro="我们收到了您找回 / 重置账号密码的请求。请在页面中输入下方验证码以设置新密码。",
        code=code,
        code_caption="密码重置验证码",
        outro=f"验证码 {ttl_minutes} 分钟内有效，仅可使用一次。",
        note="如非本人申请重置密码，请忽略本邮件，您的密码不会发生任何变化。",
    )
    body = (
        f"【{product}】密码重置验证码：{code}\n"
        f"{ttl_minutes} 分钟内有效，仅可使用一次。如非本人操作请忽略。"
    )
    return send_email(
        db,
        to=to,
        subject=f"{product} · 密码重置验证码 {code}",
        body=body,
        html=html,
    )
