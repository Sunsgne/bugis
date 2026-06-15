"""Controller cluster / HA: leader election and RIB version replication."""
from __future__ import annotations

import socket
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.controlplane import ControllerClusterNode, EvpnRoute
from app.models.enums import ControllerNodeRole


def _hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "bugis-controller"


def ensure_local_node(db: Session, node_id: str = "bugis-1") -> ControllerClusterNode:
    local = db.execute(
        select(ControllerClusterNode).where(ControllerClusterNode.is_local == 1)
    ).scalar_one_or_none()
    if local:
        return local

    # First boot: register leader + virtual standby for HA demo.
    leader = ControllerClusterNode(
        node_id=node_id,
        hostname=_hostname(),
        role=ControllerNodeRole.LEADER,
        api_url="internal://bugis",
        rib_version=0,
        is_local=1,
        last_heartbeat=datetime.now(timezone.utc),
    )
    db.add(leader)
    standby = ControllerClusterNode(
        node_id=f"{node_id}-standby",
        hostname=f"{_hostname()}-standby",
        role=ControllerNodeRole.STANDBY,
        api_url="internal://bugis-standby",
        rib_version=0,
        is_local=0,
        last_heartbeat=datetime.now(timezone.utc),
    )
    db.add(standby)
    db.commit()
    db.refresh(leader)
    return leader


def bump_rib_version(db: Session) -> int:
    local = ensure_local_node(db)
    route_count = db.execute(select(EvpnRoute)).scalars().all()
    version = len(route_count)
    local.rib_version = version
    local.last_heartbeat = datetime.now(timezone.utc)
    standby = db.execute(
        select(ControllerClusterNode).where(
            ControllerClusterNode.role == ControllerNodeRole.STANDBY
        )
    ).scalar_one_or_none()
    if standby:
        standby.rib_version = version
        standby.last_heartbeat = datetime.now(timezone.utc)
    db.flush()
    return version


def heartbeat(db: Session) -> None:
    now = datetime.now(timezone.utc)
    nodes = db.execute(select(ControllerClusterNode)).scalars().all()
    for node in nodes:
        node.last_heartbeat = now
    db.flush()


def cluster_status(db: Session) -> dict:
    nodes = db.execute(
        select(ControllerClusterNode).order_by(ControllerClusterNode.id)
    ).scalars().all()
    leader = next((n for n in nodes if n.role == ControllerNodeRole.LEADER), None)
    return {
        "mode": "active-standby",
        "leader": leader.node_id if leader else None,
        "rib_version": leader.rib_version if leader else 0,
        "nodes": [
            {
                "node_id": n.node_id,
                "hostname": n.hostname,
                "role": n.role.value,
                "api_url": n.api_url,
                "rib_version": n.rib_version,
                "is_local": bool(n.is_local),
                "last_heartbeat": n.last_heartbeat.isoformat() if n.last_heartbeat else None,
            }
            for n in nodes
        ],
    }
