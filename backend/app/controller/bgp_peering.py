"""BGP EVPN peering between Bugis controller and fabric devices."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.controlplane import BgpEvpnSession, EvpnRoute
from app.models.device import Device
from app.models.enums import BgpSessionState, OverlayTech


def _controller_asn() -> int:
    return getattr(settings, "controller_bgp_asn", 65000)


def render_peer_config(device: Device) -> str:
    peer = device.loopback_ip or device.mgmt_ip
    asn = device.bgp_asn or _controller_asn()
    lines = [
        f"# Bugis controller -> {device.name} BGP EVPN peer",
        f"router bgp {_controller_asn()}",
        " address-family l2vpn evpn",
        f"  neighbor {peer} remote-as {asn}",
        f"  neighbor {peer} update-source LoopBack0",
        f"  neighbor {peer} activate",
        f"  neighbor {peer} route-reflector-client",
    ]
    if device.overlay_tech == OverlayTech.SRMPLS_EVPN:
        lines.append(f"  neighbor {peer} advertise encap-type mpls")
    else:
        lines.append(f"  neighbor {peer} advertise encap-type vxlan")
    return "\n".join(lines)


def ensure_sessions(db: Session, devices: list[Device]) -> list[BgpEvpnSession]:
    sessions: list[BgpEvpnSession] = []
    for device in devices:
        peer_ip = device.loopback_ip or device.mgmt_ip
        sess = db.execute(
            select(BgpEvpnSession).where(BgpEvpnSession.device_id == device.id)
        ).scalar_one_or_none()
        if sess is None:
            sess = BgpEvpnSession(
                device_id=device.id,
                device_name=device.name,
                peer_ip=peer_ip,
                local_asn=_controller_asn(),
                remote_asn=device.bgp_asn,
                state=BgpSessionState.CONNECT,
            )
            db.add(sess)
        sess.device_name = device.name
        sess.peer_ip = peer_ip
        sess.remote_asn = device.bgp_asn
        sess.config_snippet = render_peer_config(device)
        sessions.append(sess)
    db.flush()
    return sessions


def sync_sessions(db: Session) -> int:
    """Refresh BGP session state from RIB (dry-run: simulate established)."""
    sessions = db.execute(select(BgpEvpnSession)).scalars().all()
    now = datetime.now(timezone.utc)
    for sess in sessions:
        rx = db.scalar(
            select(func.count(EvpnRoute.id)).where(
                EvpnRoute.origin_device_id == sess.device_id
            )
        ) or 0
        tx = db.scalar(select(func.count(EvpnRoute.id))) or 0
        sess.routes_received = int(rx)
        sess.routes_sent = int(tx)
        sess.state = BgpSessionState.ESTABLISHED if rx or tx else BgpSessionState.CONNECT
        sess.last_keepalive = now
    db.flush()
    return len(sessions)


def list_sessions(db: Session) -> list[dict]:
    rows = db.execute(
        select(BgpEvpnSession).order_by(BgpEvpnSession.id)
    ).scalars().all()
    return [
        {
            "id": s.id,
            "device_id": s.device_id,
            "device_name": s.device_name,
            "peer_ip": s.peer_ip,
            "local_asn": s.local_asn,
            "remote_asn": s.remote_asn,
            "state": s.state.value,
            "routes_received": s.routes_received,
            "routes_sent": s.routes_sent,
            "last_keepalive": s.last_keepalive.isoformat() if s.last_keepalive else None,
        }
        for s in rows
    ]
