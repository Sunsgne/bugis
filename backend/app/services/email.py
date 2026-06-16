"""Transactional email helper (MFA codes, security notifications)."""
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services import platform_settings as platform_cfg


def send_email(
    db: Session,
    *,
    to: str,
    subject: str,
    body: str,
) -> tuple[bool, str]:
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
