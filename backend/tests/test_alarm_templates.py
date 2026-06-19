"""Tests for editable alarm notification templates."""
from __future__ import annotations

from app.models.alarm import Alarm
from app.models.enums import AlarmSeverity, AlarmStatus
from app.services import alarm_messages as msg
from app.services.alarm_template_registry import (
    get_templates,
    merge_templates,
    render_template,
    save_templates,
    templates_to_dict,
)


def test_render_template_variables():
    out = render_template("专线 {{circuit_code}} 丢包 {{loss_pct}}%", {"circuit_code": "CIR-1", "loss_pct": 1.25})
    assert "CIR-1" in out
    assert "1.25" in out


def test_custom_template_overrides_title(db_session):
    base = templates_to_dict(merge_templates(None))
    base["kinds"]["sla_loss"]["title"] = "CUSTOM {{circuit_code}} loss alert"
    save_templates(db_session, base)
    copy = msg.build_circuit_loss("CIR-XYZ", 2.0, 0.5, get_templates(db_session))
    assert copy.title == "CUSTOM CIR-XYZ loss alert"


def test_notification_text_uses_custom_banner(db_session):
    data = templates_to_dict(get_templates(db_session))
    data["global"]["banner"] = "=== TEST BANNER {{product_name}} ==="
    save_templates(db_session, data)
    templates = get_templates(db_session)
    copy = msg.build_circuit_latency("CIR-002", 68.2, 50.0, templates)
    alarm = Alarm(
        kind=copy.kind,
        severity=AlarmSeverity.MINOR,
        status=AlarmStatus.ACTIVE,
        title=copy.title,
        detail=copy.detail,
        dedup_key="test",
        circuit_id=1,
    )
    text = msg.format_notification_text(alarm, copy=copy, templates=templates, product_name="Bugis")
    assert "TEST BANNER Bugis" in text
