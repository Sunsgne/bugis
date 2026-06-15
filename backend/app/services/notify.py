"""Outbound alarm notification dispatch.

Sends alarms to configured channels (generic webhook, Slack, DingTalk, WeCom)
when their severity meets the channel threshold. Dry-run aware.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.alarm import Alarm
from app.models.enums import SEVERITY_RANK, NotificationType
from app.models.notification import NotificationChannel

logger = logging.getLogger("bugis.notify")


def _format_text(alarm: Alarm) -> str:
    return (
        f"[Bugis 告警] {alarm.severity.value.upper()} | {alarm.kind}\n"
        f"{alarm.title}"
        + (f"\n详情: {alarm.detail}" if alarm.detail else "")
    )


def build_payload(channel: NotificationChannel, alarm: Alarm) -> dict:
    text = _format_text(alarm)
    if channel.type == NotificationType.SLACK:
        return {"text": text}
    if channel.type in (NotificationType.DINGTALK, NotificationType.WECOM):
        return {"msgtype": "text", "text": {"content": text}}
    if channel.type == NotificationType.FEISHU:
        return {"msg_type": "text", "content": {"text": text}}
    if channel.type == NotificationType.TEAMS:
        return {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "themeColor": "CF1322" if alarm.severity.value in ("critical", "major")
            else "1677FF",
            "title": f"[Bugis] {alarm.severity.value.upper()} · {alarm.kind}",
            "text": text,
        }
    if channel.type == NotificationType.EMAIL:
        return {
            "to": channel.url,
            "subject": f"[Bugis][{alarm.severity.value.upper()}] {alarm.title}",
            "body": text,
        }
    # generic webhook
    return {
        "source": "bugis",
        "severity": alarm.severity.value,
        "kind": alarm.kind,
        "title": alarm.title,
        "detail": alarm.detail,
        "circuit_id": alarm.circuit_id,
        "device_id": alarm.device_id,
    }


def _send(channel: NotificationChannel, payload: dict) -> tuple[bool, str]:
    if settings.dry_run:
        return True, f"[DRY-RUN] -> {channel.type.value} {channel.url}"
    if channel.type == NotificationType.EMAIL:  # pragma: no cover
        return _send_email(channel, payload)
    try:  # pragma: no cover - requires network
        import httpx

        with httpx.Client(timeout=10) as client:
            resp = client.post(channel.url, json=payload)
            return resp.is_success, f"{resp.status_code}"
    except Exception as exc:  # pragma: no cover
        return False, f"error: {exc}"


def _send_email(channel: NotificationChannel, payload: dict) -> tuple[bool, str]:  # pragma: no cover
    """Send via SMTP if BUGIS_SMTP_HOST is configured, else report skip."""
    host = getattr(settings, "smtp_host", "") or ""
    if not host:
        return False, "SMTP not configured (set BUGIS_SMTP_HOST)"
    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(payload["body"], "plain", "utf-8")
    msg["Subject"] = payload["subject"]
    msg["From"] = getattr(settings, "smtp_from", "bugis@localhost")
    msg["To"] = payload["to"]
    port = int(getattr(settings, "smtp_port", 25) or 25)
    security = (getattr(settings, "smtp_security", "starttls") or "starttls").lower()
    user = getattr(settings, "smtp_user", "") or ""
    password = getattr(settings, "smtp_password", "") or ""
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


def dispatch_for_alarm(db: Session, alarm: Alarm) -> int:
    """Send an alarm to all eligible active channels. Returns count dispatched."""
    channels = db.execute(
        select(NotificationChannel).where(NotificationChannel.active.is_(True))
    ).scalars().all()
    threshold_rank = SEVERITY_RANK.get(alarm.severity.value, 0)
    dispatched = 0
    for ch in channels:
        if SEVERITY_RANK.get(ch.min_severity.value, 0) > threshold_rank:
            continue
        ok, detail = _send(ch, build_payload(ch, alarm))
        ch.last_status = ("ok" if ok else "failed") + f": {detail}"
        ch.last_dispatch_at = datetime.now(timezone.utc)
        dispatched += 1
    return dispatched


def test_channel(db: Session, channel: NotificationChannel) -> dict:
    sample = Alarm(
        severity=channel.min_severity,
        kind="test",
        title="测试通知 / Test notification from Bugis",
        dedup_key="test",
    )
    ok, detail = _send(channel, build_payload(channel, sample))
    channel.last_status = ("ok" if ok else "failed") + f": {detail}"
    channel.last_dispatch_at = datetime.now(timezone.utc)
    return {"success": ok, "detail": detail,
            "payload": build_payload(channel, sample)}
