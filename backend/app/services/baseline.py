"""Device initialization (baseline / standard template) rendering.

Builds a vendor-correct base configuration for onboarding a device:
management (hostname/NTP/SNMP/syslog), Loopback0, underlay IGP (+ Segment
Routing for SR vendors), VXLAN/EVPN globals and the BGP EVPN overlay with
route-reflector peering.
"""
from __future__ import annotations

import os

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services import snmp_settings as snmp_cfg_service
from app.models.device import Device
from app.models.enums import DeviceRole

TEMPLATE_ROOT = os.path.join(os.path.dirname(__file__), "..", "templates")

_env = Environment(
    loader=FileSystemLoader(os.path.abspath(TEMPLATE_ROOT)),
    autoescape=select_autoescape(enabled_extensions=()),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)

# Roles that act as BGP EVPN route reflectors / overlay anchors.
RR_ROLES = {DeviceRole.RR, DeviceRole.SPINE, DeviceRole.DCI_GW, DeviceRole.BORDER_LEAF}


def _rr_peers(db: Session, device: Device) -> list[str]:
    """Loopback IPs of route reflectors in the same site (overlay anchors)."""
    if device.site_id is None:
        return []
    rows = db.execute(
        select(Device).where(
            Device.site_id == device.site_id,
            Device.id != device.id,
        )
    ).scalars().all()
    peers = [
        d.loopback_ip
        for d in rows
        if d.loopback_ip and (d.is_route_reflector or d.role in RR_ROLES)
    ]
    return peers


def build_context(db: Session, device: Device) -> dict:
    asn = device.bgp_asn or (device.site.bgp_asn if device.site else None) or 65000
    is_rr = device.is_route_reflector or device.role in RR_ROLES
    return {
        "device": device,
        "site": device.site,
        "vendor": device.vendor.value,
        "asn": asn,
        "rr_peers": _rr_peers(db, device),
        "is_rr": is_rr,
        "ntp_server": settings.baseline_ntp_server,
        "syslog_server": settings.baseline_syslog_server,
        "snmp_community": snmp_cfg_service.get_or_create(db).baseline_community,
    }


def render_baseline(db: Session, device: Device) -> str:
    ctx = build_context(db, device)
    name = f"{device.vendor.value}/baseline.j2"
    try:
        template = _env.get_template(name)
    except Exception:
        template = _env.get_template("_generic/baseline.j2")
    return template.render(**ctx)
