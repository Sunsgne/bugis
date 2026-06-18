"""Alarm message templates and auto-ack policy."""
from __future__ import annotations

from app.models.enums import AlarmSeverity
from app.services import alarm_messages as msg


def test_circuit_loss_template():
    copy = msg.build_circuit_loss("CIR-001", 1.25, 0.5)
    assert "P2" in copy.title
    assert "丢包" in copy.title
    assert "1.250%" in copy.detail
    assert copy.impact


def test_notification_text_includes_sections():
    from app.models.alarm import Alarm
    from app.models.enums import AlarmStatus

    copy = msg.build_circuit_latency("CIR-002", 68.2, 50.0)
    alarm = Alarm(
        kind=copy.kind,
        severity=AlarmSeverity.MINOR,
        status=AlarmStatus.ACTIVE,
        title=copy.title,
        detail=copy.detail,
        dedup_key="test",
        circuit_id=1,
    )
    text = msg.format_notification_text(alarm)
    assert "Bugis 智能运维告警" in text
    assert "影响评估" in text
    assert "建议处置" in text
    assert "时延越限" in text or "时延" in text


def test_auto_ack_severities():
    assert AlarmSeverity.MINOR in msg.AUTO_ACK_AFTER_NOTIFY
    assert AlarmSeverity.MAJOR not in msg.AUTO_ACK_AFTER_NOTIFY
    assert AlarmSeverity.CRITICAL not in msg.AUTO_ACK_AFTER_NOTIFY
