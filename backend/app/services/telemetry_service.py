"""Telemetry & SLA computation from southbound-collected samples."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit
from app.models.enums import CircuitStatus
from app.models.telemetry import TelemetrySample
from app.schemas.telemetry import CircuitHealth
from app.services import availability_service, snmp_telemetry, telemetry_timescale

# Probe rows carry QoS only (latency/jitter/loss); rx/tx are always 0 and must not
# appear in traffic charts or bandwidth billing.
_TRAFFIC_EXCLUDED_SOURCES = frozenset({"probe"})


def _is_traffic_sample(sample: TelemetrySample) -> bool:
    return sample.source not in _TRAFFIC_EXCLUDED_SOURCES


def traffic_samples(samples: list[TelemetrySample]) -> list[TelemetrySample]:
    """Samples that carry SNMP (or manual) traffic counters."""
    return [s for s in samples if _is_traffic_sample(s)]


def record_sample(db: Session, **kwargs) -> TelemetrySample:
    if not kwargs.get("source"):
        kwargs["source"] = "manual"
    sample = TelemetrySample(**kwargs)
    db.add(sample)
    db.flush()
    return sample


def _latest_probe_qos(db: Session, circuit_id: int, *, max_age_sec: int = 3600) -> TelemetrySample | None:
    since = datetime.now(timezone.utc) - timedelta(seconds=max_age_sec)
    return db.execute(
        select(TelemetrySample)
        .where(
            TelemetrySample.circuit_id == circuit_id,
            TelemetrySample.source == "probe",
            TelemetrySample.created_at >= since,
        )
        .order_by(TelemetrySample.created_at.desc(), TelemetrySample.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def collect_circuit_sample(
    db: Session,
    circuit: Circuit,
    *,
    interval_sec: float = 30.0,
) -> TelemetrySample | None:
    """Collect traffic via SNMP; QoS metrics only from recent on-demand/scheduled probes."""
    traffic = snmp_telemetry.poll_circuit_traffic(
        db, circuit, interval_sec=interval_sec
    )
    if traffic.source == "unavailable":
        return None

    latency = jitter = loss = 0.0
    if circuit.latency_probe_enabled:
        probe = _latest_probe_qos(db, circuit.id)
        latency = probe.latency_ms if probe else 0.0
        jitter = probe.jitter_ms if probe else 0.0
        loss = probe.packet_loss_pct if probe else 0.0
    state = "up" if traffic.tunnel_up else "down"

    sample = record_sample(
        db,
        circuit_id=circuit.id,
        rx_mbps=traffic.rx_mbps,
        tx_mbps=traffic.tx_mbps,
        utilization_pct=traffic.utilization_pct,
        latency_ms=latency,
        jitter_ms=jitter,
        packet_loss_pct=loss,
        errors=traffic.errors,
        tunnel_state=state,
        source=traffic.source,
    )
    availability_service.process_tunnel_state(
        db,
        circuit,
        tunnel_up=traffic.tunnel_up,
        source=traffic.source,
        at=sample.created_at,
    )
    return sample


def list_circuit_samples(
    db: Session,
    circuit_id: int,
    *,
    limit: int = 120,
    hours: int | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    traffic_only: bool = False,
) -> list[TelemetrySample]:
    """Return samples oldest-first for charting."""
    limit = max(1, min(limit, 5000))
    stmt = select(TelemetrySample).where(TelemetrySample.circuit_id == circuit_id)
    if traffic_only:
        stmt = stmt.where(TelemetrySample.source.notin_(_TRAFFIC_EXCLUDED_SOURCES))
    if start_at and end_at:
        start = start_at.astimezone(timezone.utc) if start_at.tzinfo else start_at.replace(tzinfo=timezone.utc)
        end = end_at.astimezone(timezone.utc) if end_at.tzinfo else end_at.replace(tzinfo=timezone.utc)
        stmt = stmt.where(
            TelemetrySample.created_at >= start,
            TelemetrySample.created_at <= end,
        )
    elif hours is not None:
        since = datetime.now(timezone.utc) - timedelta(hours=max(1, min(hours, 24 * 366)))
        stmt = stmt.where(TelemetrySample.created_at >= since)
    # Newest samples first, then reverse so charts receive oldest-first series.
    stmt = stmt.order_by(TelemetrySample.created_at.desc(), TelemetrySample.id.desc()).limit(limit)
    rows = list(db.execute(stmt).scalars().all())
    rows.reverse()
    return rows


def _window_hours(
    *,
    hours: int | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> int:
    if start_at and end_at:
        start = start_at.astimezone(timezone.utc) if start_at.tzinfo else start_at.replace(tzinfo=timezone.utc)
        end = end_at.astimezone(timezone.utc) if end_at.tzinfo else end_at.replace(tzinfo=timezone.utc)
        return max(1, int((end - start).total_seconds() // 3600))
    return max(1, hours or 24)


def _bucket_traffic_sample(circuit_id: int, bucket: dict) -> dict:
    ts = bucket["bucket"]
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return {
        "id": 0,
        "circuit_id": circuit_id,
        "rx_mbps": bucket["rx_mbps"],
        "tx_mbps": bucket["tx_mbps"],
        "utilization_pct": 0.0,
        "latency_ms": 0.0,
        "jitter_ms": 0.0,
        "packet_loss_pct": 0.0,
        "errors": 0,
        "tunnel_state": "up",
        "source": "aggregate_5m",
        "created_at": ts,
    }


def _bucket_qos_sample(circuit_id: int, bucket: dict) -> dict:
    ts = bucket["bucket"]
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return {
        "id": 0,
        "circuit_id": circuit_id,
        "rx_mbps": 0.0,
        "tx_mbps": 0.0,
        "utilization_pct": 0.0,
        "latency_ms": bucket["latency_ms"],
        "jitter_ms": 0.0,
        "packet_loss_pct": 0.0,
        "errors": 0,
        "tunnel_state": "up",
        "source": "probe",
        "created_at": ts,
    }


def _sample_field(sample: TelemetrySample | dict, field: str, default: float = 0.0) -> float:
    if isinstance(sample, dict):
        return float(sample.get(field, default) or default)
    return float(getattr(sample, field, default) or default)


def chart_p95(samples: list[TelemetrySample] | list[dict]) -> dict:
    traffic = [
        s for s in samples
        if (s.get("source") if isinstance(s, dict) else s.source) not in _TRAFFIC_EXCLUDED_SOURCES
    ]
    rx = [_sample_field(s, "rx_mbps") for s in traffic]
    tx = [_sample_field(s, "tx_mbps") for s in traffic]
    rx95 = _percentile(rx, 95)
    tx95 = _percentile(tx, 95)
    return {
        "in_95_mbps": rx95,
        "out_95_mbps": tx95,
        "billable_95_mbps": max(rx95, tx95),
    }


def traffic_summary_payload(
    db: Session,
    circuit: Circuit,
    *,
    limit: int = 120,
    hours: int | None = 24,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> dict:
    """SNMP traffic series for Rx/Tx charts plus probe QoS series for latency charts."""
    eff_hours = _window_hours(hours=hours, start_at=start_at, end_at=end_at)
    use_ca = (
        telemetry_timescale.continuous_aggregate_available(db)
        and telemetry_timescale.should_use_continuous_aggregate(eff_hours)
    )

    kwargs = {
        "limit": limit,
        "hours": hours if not (start_at and end_at) else None,
        "start_at": start_at,
        "end_at": end_at,
    }

    def _raw_summary() -> tuple[list, list]:
        traffic = list_circuit_samples(db, circuit.id, traffic_only=True, **kwargs)
        qos: list = []
        if circuit.latency_probe_enabled:
            qos = [
                s
                for s in list_circuit_samples(db, circuit.id, traffic_only=False, **kwargs)
                if s.source == "probe"
            ]
        return traffic, qos

    if use_ca:
        traffic_rows = [
            _bucket_traffic_sample(circuit.id, b)
            for b in telemetry_timescale.fetch_traffic_buckets(
                db, circuit_id=circuit.id, hours=eff_hours
            )
        ]
        qos_rows: list = []
        if circuit.latency_probe_enabled:
            qos_rows = [
                _bucket_qos_sample(circuit.id, b)
                for b in telemetry_timescale.fetch_latency_buckets(
                    db, circuit_id=circuit.id, hours=eff_hours
                )
            ]
        # Newly provisioned circuits may have raw samples before the 5m CA refreshes.
        used_raw_fallback = False
        if not traffic_rows or (circuit.latency_probe_enabled and not qos_rows):
            raw_traffic, raw_qos = _raw_summary()
            if not traffic_rows and raw_traffic:
                traffic_rows = raw_traffic
                used_raw_fallback = True
            if circuit.latency_probe_enabled and not qos_rows and raw_qos:
                qos_rows = raw_qos
                used_raw_fallback = True
        resolution = "raw" if used_raw_fallback else "5m_aggregate"
    else:
        traffic_rows, qos_rows = _raw_summary()
        resolution = "raw"

    p95 = chart_p95(traffic_rows) if traffic_rows else {
        "in_95_mbps": 0.0,
        "out_95_mbps": 0.0,
        "billable_95_mbps": 0.0,
    }
    return {
        "circuit_id": circuit.id,
        "samples": traffic_rows,
        "qos_samples": qos_rows,
        "p95": p95,
        "bandwidth_mbps": circuit.bandwidth_mbps,
        "resolution": resolution,
    }


def _aggregate_overview_traffic(rows: list[TelemetrySample]) -> list[dict]:
    """Bucket samples by minute and circuit, then sum per-circuit averages."""
    per_circuit: dict[tuple[str, int], dict] = {}
    for s in rows:
        if not s.created_at or s.circuit_id is None:
            continue
        minute = s.created_at.strftime("%Y-%m-%d %H:%M")
        key = (minute, s.circuit_id)
        b = per_circuit.setdefault(
            key, {"rx": 0.0, "tx": 0.0, "lat": 0.0, "loss": 0.0, "n": 0, "lat_n": 0}
        )
        if _is_traffic_sample(s):
            b["rx"] += s.rx_mbps
            b["tx"] += s.tx_mbps
            b["n"] += 1
        elif s.source == "probe":
            b["lat"] += s.latency_ms
            b["loss"] += s.packet_loss_pct
            b["lat_n"] += 1

    buckets: dict[str, dict] = {}
    for (minute, _), vals in per_circuit.items():
        b = buckets.setdefault(
            minute,
            {"rx": 0.0, "tx": 0.0, "lat": 0.0, "loss": 0.0, "n": 0, "lat_n": 0},
        )
        if vals["n"] > 0:
            b["rx"] += vals["rx"] / vals["n"]
            b["tx"] += vals["tx"] / vals["n"]
        if vals["lat_n"] > 0:
            b["lat"] += vals["lat"]
            b["loss"] += vals["loss"]
            b["lat_n"] += vals["lat_n"]
        b["n"] += vals["n"]

    out = []
    for minute in sorted(buckets):
        b = buckets[minute]
        lat_n = max(b["lat_n"], 1)
        out.append({
            "t": minute[11:],
            "rx": round(b["rx"], 1),
            "tx": round(b["tx"], 1),
            "latency": round(b["lat"] / lat_n, 2) if b["lat_n"] else None,
            "loss": round(b["loss"] / lat_n, 3) if b["lat_n"] else None,
        })
    return out


def overview_traffic(
    db: Session,
    *,
    sample_limit: int = 2000,
    hours: int = 24,
) -> list[dict]:
    """Aggregate recent telemetry into a per-minute network-wide traffic trend."""
    eff_hours = max(1, min(hours, 24 * 7))
    if (
        telemetry_timescale.continuous_aggregate_available(db)
        and telemetry_timescale.should_use_continuous_aggregate(eff_hours)
    ):
        buckets = telemetry_timescale.fetch_network_overview_buckets(
            db, hours=eff_hours
        )
        if buckets:
            return buckets

    since = datetime.now(timezone.utc) - timedelta(hours=eff_hours)
    rows = db.execute(
        select(TelemetrySample)
        .where(TelemetrySample.created_at >= since)
        .order_by(TelemetrySample.created_at.desc(), TelemetrySample.id.desc())
        .limit(sample_limit)
    ).scalars().all()
    return _aggregate_overview_traffic(rows)[-40:]


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    import math
    idx = max(0, math.ceil(pct / 100 * len(s)) - 1)
    return round(s[idx], 2)


def _month_bounds(period: str) -> tuple[datetime, datetime]:
    year, month = (int(p) for p in period.split("-", 1))
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


def billing_95th(db: Session, circuit: Circuit, period: str | None = None) -> dict:
    """95th-percentile (月95) bandwidth billing for a circuit."""
    timestamps = db.execute(
        select(TelemetrySample.created_at).where(
            TelemetrySample.circuit_id == circuit.id,
            TelemetrySample.created_at.is_not(None),
        )
    ).scalars().all()
    months = sorted({ts.strftime("%Y-%m") for ts in timestamps}, reverse=True)
    if telemetry_timescale.continuous_aggregate_available(db):
        ca_months = telemetry_timescale.fetch_billing_months(db, circuit_id=circuit.id)
        months = sorted(set(months) | set(ca_months), reverse=True)
    sel = period if period in months else (months[0] if months else None)
    if not sel:
        return {
            "circuit_id": circuit.id,
            "circuit_code": circuit.code,
            "period": None,
            "available_months": [],
            "samples": 0,
            "bandwidth_mbps": circuit.bandwidth_mbps,
            "in_95_mbps": 0.0,
            "out_95_mbps": 0.0,
            "billable_95_mbps": 0.0,
            "peak_mbps": 0.0,
            "avg_mbps": 0.0,
            "utilization_pct": 0.0,
        }

    start, end = _month_bounds(sel)
    if telemetry_timescale.continuous_aggregate_available(db):
        agg = telemetry_timescale.fetch_billing_95th_from_aggregate(
            db, circuit_id=circuit.id, month_start=start, month_end=end
        )
        rx95 = agg["in_95_mbps"]
        tx95 = agg["out_95_mbps"]
        sample_count = agg["samples"]
        peak = agg["peak_mbps"]
        avg = agg["avg_mbps"]
    else:
        rows = db.execute(
            select(TelemetrySample).where(
                TelemetrySample.circuit_id == circuit.id,
                TelemetrySample.created_at >= start,
                TelemetrySample.created_at < end,
            )
        ).scalars().all()
        traffic = traffic_samples(rows)
        rx = [s.rx_mbps for s in traffic]
        tx = [s.tx_mbps for s in traffic]
        rx95 = _percentile(rx, 95)
        tx95 = _percentile(tx, 95)
        sample_count = len(traffic)
        peak = round(max([*rx, *tx], default=0.0), 2)
        avg = round((sum(rx) + sum(tx)) / (2 * len(rows)), 2) if rows else 0.0

    billable = max(rx95, tx95)
    return {
        "circuit_id": circuit.id,
        "circuit_code": circuit.code,
        "period": sel,
        "available_months": months,
        "samples": sample_count,
        "bandwidth_mbps": circuit.bandwidth_mbps,
        "in_95_mbps": rx95,
        "out_95_mbps": tx95,
        "billable_95_mbps": billable,
        "peak_mbps": peak,
        "avg_mbps": avg,
        "utilization_pct": round(billable / circuit.bandwidth_mbps * 100, 1)
        if circuit.bandwidth_mbps else 0.0,
    }


def compute_health(
    db: Session,
    circuit: Circuit,
    *,
    limit: int = 100,
    hours: int | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> CircuitHealth:
    windowed = hours is not None or (start_at is not None and end_at is not None)
    if windowed:
        samples = list_circuit_samples(
            db,
            circuit.id,
            limit=limit,
            hours=hours,
            start_at=start_at,
            end_at=end_at,
        )
        latest = samples[-1] if samples else None
    else:
        samples = list(
            db.execute(
                select(TelemetrySample)
                .where(TelemetrySample.circuit_id == circuit.id)
                .order_by(TelemetrySample.id.desc())
                .limit(limit)
            ).scalars().all()
        )
        latest = samples[0] if samples else None

    n = len(samples)
    qos_samples = (
        [s for s in samples if s.source == "probe"]
        if circuit.latency_probe_enabled
        else []
    )
    traffic_rows = traffic_samples(samples)
    sources = sorted({s.source for s in samples if s.source})

    if n == 0:
        return CircuitHealth(
            circuit_id=circuit.id,
            circuit_code=circuit.code,
            status=circuit.status.value,
            sla_target=circuit.sla_target,
            bandwidth_mbps=circuit.bandwidth_mbps,
            samples=0,
            health_score=100.0 if circuit.status == CircuitStatus.ACTIVE else 0.0,
            data_sources=[],
        )

    avg_util = sum(s.utilization_pct for s in traffic_rows) / max(len(traffic_rows), 1)
    peak_util = max((s.utilization_pct for s in traffic_rows), default=0.0)
    latest_traffic = traffic_rows[-1] if traffic_rows else None
    tunnel_down = bool(
        (latest_traffic and latest_traffic.tunnel_state == "down")
        or (not latest_traffic and latest and latest.tunnel_state == "down")
    )

    avg_lat = avg_jit = avg_loss = 0.0
    if qos_samples:
        qn = len(qos_samples)
        avg_lat = sum(s.latency_ms for s in qos_samples) / qn
        avg_jit = sum(s.jitter_ms for s in qos_samples) / qn
        avg_loss = sum(s.packet_loss_pct for s in qos_samples) / qn

    score = 100.0
    if qos_samples:
        score -= min(avg_loss * 40, 40)
        score -= min(max(avg_lat - 10, 0) * 1.5, 20)
        score -= min(avg_jit * 3, 15)
    score -= min(max(peak_util - 90, 0) * 1.0, 15)
    if circuit.status != CircuitStatus.ACTIVE:
        score = min(score, 50)
    if tunnel_down:
        score = min(score, 30)
    score = max(0.0, round(score, 1))

    return CircuitHealth(
        circuit_id=circuit.id,
        circuit_code=circuit.code,
        status=circuit.status.value,
        sla_target=circuit.sla_target,
        avg_latency_ms=round(avg_lat, 2),
        avg_jitter_ms=round(avg_jit, 2),
        avg_packet_loss_pct=round(avg_loss, 3),
        avg_utilization_pct=round(avg_util, 2),
        peak_utilization_pct=round(peak_util, 2),
        bandwidth_mbps=circuit.bandwidth_mbps,
        samples=n,
        qos_samples=len(qos_samples),
        data_sources=sources,
        health_score=score,
        tunnel_down=tunnel_down,
    )
