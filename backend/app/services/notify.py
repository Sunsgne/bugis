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
from app.models.enums import AlarmSeverity, AlarmStatus, SEVERITY_RANK, NotificationType
from app.models.notification import NotificationChannel
from app.services import alarm_messages as msg
from app.services.alarm_email_templates import render_alarm_email
from app.services.alarm_template_registry import get_templates, render_template
from app.services.platform_settings import get_or_create

logger = logging.getLogger("bugis.notify")


def build_payload(channel: NotificationChannel, alarm: Alarm, db: Session) -> dict:
    templates = get_templates(db)
    plat = get_or_create(db)
    product = plat.product_name or "Bugis Network"
    text = msg.format_notification_text(alarm, templates=templates, product_name=product)
    structured = msg.format_notification_payload(alarm, templates=templates)
    copy = msg.copy_from_alarm(alarm, templates)
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
            "title": structured["title"],
            "text": text.replace("\n", "<br/>"),
        }
    if channel.type == NotificationType.EMAIL:
        sev = msg.severity_label(alarm.severity.value)
        ctx = {
            "product_name": product,
            "severity_label": sev,
            "title": copy.title,
        }
        subject = render_template(templates.global_.email_subject, ctx)
        payload: dict = {
            "to": channel.url,
            "subject": subject,
            "body": text,
        }
        if templates.global_.html_enabled:
            payload["html"] = render_alarm_email(plat, alarm, copy=copy, templates=templates, plain_body=text)
        return payload
    return structured


def _send(channel: NotificationChannel, payload: dict) -> tuple[bool, str]:
    if settings.dry_run:
        return True, f"[DRY-RUN] -> {channel.type.value} {channel.url}"
    if channel.type == NotificationType.EMAIL:  # pragma: no cover
        return _send_email(channel, payload)
    try:  # pragma: no cover - requires network
        import httpx

        from app.core.url_validation import validate_outbound_http_url

        safe_url = validate_outbound_http_url(channel.url, field="channel.url")
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            resp = client.post(safe_url, json=payload)
            return resp.is_success, f"{resp.status_code}"
    except ValueError as exc:
        return False, f"blocked url: {exc}"
    except Exception as exc:  # pragma: no cover
        return False, f"error: {exc}"


def _send_email(channel: NotificationChannel, payload: dict) -> tuple[bool, str]:  # pragma: no cover
    """Send via SMTP if BUGIS_SMTP_HOST is configured, else report skip."""
    host = getattr(settings, "smtp_host", "") or ""
    if not host:
        return False, "SMTP not configured (set BUGIS_SMTP_HOST)"
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    if payload.get("html"):
        msg_obj = MIMEMultipart("alternative")
        msg_obj.attach(MIMEText(payload["body"], "plain", "utf-8"))
        msg_obj.attach(MIMEText(payload["html"], "html", "utf-8"))
    else:
        msg_obj = MIMEText(payload["body"], "plain", "utf-8")
    msg_obj["Subject"] = payload["subject"]
    msg_obj["From"] = getattr(settings, "smtp_from", "bugis@localhost")
    msg_obj["To"] = payload["to"]
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
            s.send_message(msg_obj)
        return True, "sent"
    except Exception as exc:
        return False, f"smtp error: {exc}"


def auto_acknowledge_after_notify(db: Session, alarm: Alarm) -> bool:
    """Auto-ack lower-severity alarms once at least one channel accepted delivery."""
    if alarm.status != AlarmStatus.ACTIVE:
        return False
    if alarm.severity not in msg.AUTO_ACK_AFTER_NOTIFY:
        return False
    alarm.status = AlarmStatus.ACKNOWLEDGED
    alarm.acknowledged_by = msg.AUTO_ACK_ACTOR
    db.flush()
    return True


def dispatch_for_alarm(db: Session, alarm: Alarm) -> int:
    """Send an alarm to all eligible active channels. Returns count dispatched."""
    channels = db.execute(
        select(NotificationChannel).where(NotificationChannel.active.is_(True))
    ).scalars().all()
    threshold_rank = SEVERITY_RANK.get(alarm.severity.value, 0)
    dispatched = 0
    delivered = 0
    for ch in channels:
        if SEVERITY_RANK.get(ch.min_severity.value, 0) > threshold_rank:
            continue
        ok, detail = _send(ch, build_payload(ch, alarm, db))
        ch.last_status = ("ok" if ok else "failed") + f": {detail}"
        ch.last_dispatch_at = datetime.now(timezone.utc)
        dispatched += 1
        if ok:
            delivered += 1
    if delivered > 0:
        auto_acknowledge_after_notify(db, alarm)
    return dispatched


def test_channel(db: Session, channel: NotificationChannel) -> dict:
    templates = get_templates(db)
    copy = msg.build_test_notification(templates)
    sample = Alarm(
        severity=channel.min_severity,
        kind=copy.kind,
        title=copy.title,
        detail=copy.detail,
        dedup_key="test",
    )
    payload = build_payload(channel, sample, db)
    ok, detail = _send(channel, payload)
    channel.last_status = ("ok" if ok else "failed") + f": {detail}"
    channel.last_dispatch_at = datetime.now(timezone.utc)
    return {"success": ok, "detail": detail, "payload": payload}
