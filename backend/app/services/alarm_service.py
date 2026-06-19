"""Alarm generation, de-duplication and lifecycle.

Alarms are raised from telemetry / capacity evaluation. A `dedup_key` ensures
a given condition produces a single active alarm until it clears.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.alarm import Alarm
from app.models.availability import CircuitAvailabilityEvent
from app.models.circuit import Circuit
from app.models.enums import AlarmSeverity, AlarmStatus, CircuitStatus
from app.models.link import Link
from app.schemas.telemetry import CircuitHealth
from app.services import platform_settings as platform_cfg
from app.services.circuit_alarm_settings import effective_thresholds
from app.services import alarm_messages as msg
from app.services.alarm_context import circuit_alarm_context, link_alarm_context
from app.services.alarm_template_registry import get_templates


def _active_by_key(db: Session, dedup_key: str) -> Alarm | None:
    return db.execute(
        select(Alarm).where(
            Alarm.dedup_key == dedup_key,
            Alarm.status != AlarmStatus.CLEARED,
        )
    ).scalar_one_or_none()


def raise_alarm(
    db: Session,
    kind: str,
    severity: AlarmSeverity,
    title: str,
    dedup_key: str,
    detail: str | None = None,
    circuit_id: int | None = None,
    device_id: int | None = None,
) -> Alarm | None:
    """Raise an alarm unless an identical active one already exists."""
    if _active_by_key(db, dedup_key):
        return None
    alarm = Alarm(
        kind=kind,
        severity=severity,
        status=AlarmStatus.ACTIVE,
        title=title,
        detail=detail,
        dedup_key=dedup_key,
        circuit_id=circuit_id,
        device_id=device_id,
    )
    db.add(alarm)
    db.flush()
    # Best-effort outbound notification dispatch (never breaks alarm raising).
    try:
        from app.services import notify

        notify.dispatch_for_alarm(db, alarm)
    except Exception:  # noqa: BLE001
        pass
    return alarm


def clear_by_key(db: Session, dedup_key: str) -> int:
    """Auto-clear active alarms whose condition no longer holds."""
    rows = db.execute(
        select(Alarm).where(
            Alarm.dedup_key == dedup_key,
            Alarm.status != AlarmStatus.CLEARED,
        )
    ).scalars().all()
    for a in rows:
        a.status = AlarmStatus.CLEARED
    return len(rows)


def evaluate_circuit_health(db: Session, circuit: Circuit, health: CircuitHealth) -> None:
    """Raise/clear alarms for one circuit based on its computed health."""
    cid = circuit.id
    plat = platform_cfg.get_or_create(db)
    th = effective_thresholds(circuit, plat)
    templates = get_templates(db)
    ctx = circuit_alarm_context(db, circuit)

    # Tunnel / status down — also check latest telemetry tunnel_state
    key_down = f"circuit:{cid}:down"
    latest_down = health.tunnel_down
    if circuit.status in (CircuitStatus.FAILED, CircuitStatus.DEGRADED) or latest_down:
        copy = msg.build_circuit_tunnel_down(
            circuit.code, circuit.status.value, templates, **ctx
        )
        raise_alarm(
            db, "tunnel_down", AlarmSeverity.CRITICAL,
            copy.title,
            key_down, detail=copy.detail, circuit_id=cid,
        )
    else:
        clear_by_key(db, key_down)

    if health.samples == 0:
        return

    # Packet loss / latency — only when path probes are enabled for this circuit.
    key_loss = f"circuit:{cid}:loss"
    key_lat = f"circuit:{cid}:latency"
    if circuit.latency_probe_enabled:
        if health.avg_packet_loss_pct > th.packet_loss_pct:
            copy = msg.build_circuit_loss(
                circuit.code, health.avg_packet_loss_pct, th.packet_loss_pct, templates, **ctx
            )
            raise_alarm(
                db, "sla_loss", AlarmSeverity.MAJOR,
                copy.title,
                key_loss, detail=copy.detail,
                circuit_id=cid,
            )
        else:
            clear_by_key(db, key_loss)

        if health.avg_latency_ms > th.latency_ms:
            copy = msg.build_circuit_latency(
                circuit.code, health.avg_latency_ms, th.latency_ms, templates, **ctx
            )
            raise_alarm(
                db, "sla_latency", AlarmSeverity.MINOR,
                copy.title,
                key_lat, detail=copy.detail,
                circuit_id=cid,
            )
        else:
            clear_by_key(db, key_lat)
    else:
        clear_by_key(db, key_loss)
        clear_by_key(db, key_lat)

    # Utilization
    key_util = f"circuit:{cid}:utilization"
    if health.peak_utilization_pct > th.utilization_pct:
        copy = msg.build_circuit_utilization(
            circuit.code, health.peak_utilization_pct, th.utilization_pct, templates, **ctx
        )
        raise_alarm(
            db, "utilization", AlarmSeverity.MINOR,
            copy.title,
            key_util, detail=copy.detail, circuit_id=cid,
        )
    else:
        clear_by_key(db, key_util)

    # Composite health score
    key_health = f"circuit:{cid}:health"
    if health.health_score < th.health_score_min:
        copy = msg.build_circuit_health(
            circuit.code, health.health_score, th.health_score_min, templates, **ctx
        )
        raise_alarm(
            db, "health", AlarmSeverity.MAJOR,
            copy.title,
            key_health, detail=copy.detail,
            circuit_id=cid,
        )
    else:
        clear_by_key(db, key_health)


def evaluate_circuit_availability(db: Session, circuit: Circuit) -> None:
    """Raise/clear interruption and flap alarms from availability events."""
    from app.services import availability_service

    cid = circuit.id
    open_ev = db.execute(
        select(CircuitAvailabilityEvent).where(
            CircuitAvailabilityEvent.circuit_id == cid,
            CircuitAvailabilityEvent.ended_at.is_(None),
        )
    ).scalar_one_or_none()

    templates = get_templates(db)
    ctx = circuit_alarm_context(db, circuit)
    key_interrupt = f"circuit:{cid}:interruption"
    if open_ev and open_ev.kind == "interruption":
        copy = msg.build_circuit_interruption(
            circuit.code, open_ev.detail, templates, **ctx
        )
        raise_alarm(
            db,
            "circuit_interruption",
            AlarmSeverity.CRITICAL,
            copy.title,
            key_interrupt,
            detail=copy.detail,
            circuit_id=cid,
        )
    else:
        clear_by_key(db, key_interrupt)

    flaps = availability_service.flap_count(db, cid)
    key_flap = f"circuit:{cid}:flap"
    if flaps >= availability_service.FLAP_COUNT_THRESHOLD:
        copy = msg.build_circuit_flap(
            circuit.code, flaps, availability_service.FLAP_WINDOW_MIN, templates, **ctx
        )
        raise_alarm(
            db,
            "circuit_flap",
            AlarmSeverity.MAJOR,
            copy.title,
            key_flap,
            detail=copy.detail,
            circuit_id=cid,
        )
    else:
        clear_by_key(db, key_flap)


def evaluate_link_health(db: Session, link: Link, health) -> None:
    """Raise/clear backbone link utilization alarms from interface telemetry."""
    from app.services import link_alarm_settings, platform_settings as platform_cfg

    key_util = f"link:{link.id}:utilization"
    if health.samples == 0:
        return
    plat = platform_cfg.get_or_create(db)
    threshold = link_alarm_settings.effective_utilization_threshold(link, plat)
    templates = get_templates(db)
    link_ctx = link_alarm_context(db, link)
    if health.peak_utilization_pct > threshold:
        copy = msg.build_link_utilization(
            link.name,
            health.peak_utilization_pct,
            threshold,
            capacity_mbps=health.capacity_mbps,
            traffic_mbps=health.traffic_mbps,
            templates=templates,
            **link_ctx,
        )
        raise_alarm(
            db,
            "link_utilization",
            AlarmSeverity.MAJOR,
            copy.title,
            key_util,
            detail=copy.detail,
            device_id=link.device_a_id,
        )
    else:
        clear_by_key(db, key_util)


def acknowledge(db: Session, alarm: Alarm, actor: str) -> Alarm:
    if alarm.status == AlarmStatus.ACTIVE:
        alarm.status = AlarmStatus.ACKNOWLEDGED
        alarm.acknowledged_by = actor
    return alarm


def clear(db: Session, alarm: Alarm) -> Alarm:
    alarm.status = AlarmStatus.CLEARED
    return alarm


def clear_active_for_circuit(db: Session, circuit: Circuit) -> int:
    """Clear all non-cleared alarms for a circuit (e.g. after decommission)."""
    rows = db.execute(
        select(Alarm).where(
            Alarm.circuit_id == circuit.id,
            Alarm.status != AlarmStatus.CLEARED,
        )
    ).scalars().all()
    for alarm in rows:
        alarm.status = AlarmStatus.CLEARED
    return len(rows)
