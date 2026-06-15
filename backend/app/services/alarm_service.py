"""Alarm generation, de-duplication and lifecycle.

Alarms are raised from telemetry / capacity evaluation. A `dedup_key` ensures
a given condition produces a single active alarm until it clears.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.alarm import Alarm
from app.models.circuit import Circuit
from app.models.enums import AlarmSeverity, AlarmStatus, CircuitStatus
from app.models.link import Link
from app.schemas.telemetry import CircuitHealth


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

    # Tunnel / status down
    key_down = f"circuit:{cid}:down"
    if circuit.status in (CircuitStatus.FAILED, CircuitStatus.DEGRADED):
        raise_alarm(
            db, "tunnel_down", AlarmSeverity.CRITICAL,
            f"专线 {circuit.code} 状态异常 ({circuit.status.value})",
            key_down, circuit_id=cid,
        )
    else:
        clear_by_key(db, key_down)

    if health.samples == 0:
        return

    # Packet loss
    key_loss = f"circuit:{cid}:loss"
    if health.avg_packet_loss_pct > settings.threshold_packet_loss_pct:
        raise_alarm(
            db, "sla_loss", AlarmSeverity.MAJOR,
            f"专线 {circuit.code} 丢包率超阈值 {health.avg_packet_loss_pct}%",
            key_loss, detail=f"threshold={settings.threshold_packet_loss_pct}%",
            circuit_id=cid,
        )
    else:
        clear_by_key(db, key_loss)

    # Latency
    key_lat = f"circuit:{cid}:latency"
    if health.avg_latency_ms > settings.threshold_latency_ms:
        raise_alarm(
            db, "sla_latency", AlarmSeverity.MINOR,
            f"专线 {circuit.code} 时延超阈值 {health.avg_latency_ms}ms",
            key_lat, circuit_id=cid,
        )
    else:
        clear_by_key(db, key_lat)

    # Utilization
    key_util = f"circuit:{cid}:utilization"
    if health.peak_utilization_pct > settings.threshold_utilization_pct:
        raise_alarm(
            db, "utilization", AlarmSeverity.MINOR,
            f"专线 {circuit.code} 带宽利用率峰值 {health.peak_utilization_pct}%",
            key_util, detail="考虑扩容带宽", circuit_id=cid,
        )
    else:
        clear_by_key(db, key_util)

    # Composite health score
    key_health = f"circuit:{cid}:health"
    if health.health_score < settings.threshold_health_score:
        raise_alarm(
            db, "health", AlarmSeverity.MAJOR,
            f"专线 {circuit.code} 健康评分偏低 ({health.health_score})",
            key_health, circuit_id=cid,
        )
    else:
        clear_by_key(db, key_health)


def evaluate_link_health(db: Session, link: Link, health) -> None:
    """Raise/clear backbone link utilization alarms from interface telemetry."""
    key_util = f"link:{link.id}:utilization"
    if health.samples == 0:
        return
    if health.peak_utilization_pct > settings.threshold_link_utilization_pct:
        raise_alarm(
            db,
            "link_utilization",
            AlarmSeverity.MAJOR,
            f"骨干链路 {link.name} 利用率 {health.peak_utilization_pct}%",
            key_util,
            detail=(
                f"阈值 {settings.threshold_link_utilization_pct}% · "
                f"容量 {health.capacity_mbps} Mbps · "
                f"峰值流量 {health.traffic_mbps} Mbps"
            ),
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
