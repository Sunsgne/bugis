"""Suggest optimal backbone links between devices based on discovered interfaces.

Backbone / DCI links use L3 VLAN interfaces (H3C Vlan-interface, Huawei Vlanif),
not customer L2 sub-interfaces or access physical ports.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device, DeviceInterface
from app.models.enums import DeviceRole, LinkType
from app.models.link import Link
from app.models.site import Site
from app.services.bw_parser import parse_bw_mbps
from app.services.link_monitor import capacity_from_interface
from app.services.port_inventory import is_huawei_subinterface, is_vlan_interface_name

_UPSTREAM_HINTS = re.compile(
    r"uplink|backbone|dci|trunk|core|peer|ix|transit|互联|上联|骨干|border|spine",
    re.IGNORECASE,
)
_CUSTOMER_HINTS = re.compile(
    r"svr:|customer|cus-|接入|客户|service-instance|vmni|demo",
    re.IGNORECASE,
)
_SYSTEM_IFACE = re.compile(
    r"loop(?:back)?|null0|inloop|console|register|meth\d|management|mgmt",
    re.IGNORECASE,
)
_BRIDGE_AGG = re.compile(r"^Bridge-Aggregation\d+$", re.IGNORECASE)

_ROLE_PRIORITY: dict[DeviceRole, int] = {
    DeviceRole.DCI_GW: 0,
    DeviceRole.BORDER_LEAF: 1,
    DeviceRole.PE: 2,
    DeviceRole.SPINE: 3,
    DeviceRole.P: 4,
    DeviceRole.VTEP: 5,
    DeviceRole.RR: 6,
    DeviceRole.LEAF: 7,
    DeviceRole.CPE: 8,
}


@dataclass
class ScoredInterface:
    name: str
    speed_mbps: int
    oper_status: str | None
    score: float
    reason: str
    kind: str = "physical"
    description: str | None = None


def is_vlan_interface(name: str) -> bool:
    return is_vlan_interface_name(name)


def is_bridge_aggregation(name: str) -> bool:
    return bool(_BRIDGE_AGG.match(name.strip()))


def _interface_kind(name: str) -> str:
    if is_vlan_interface(name):
        return "vlan"
    if is_bridge_aggregation(name):
        return "lag"
    if is_huawei_subinterface(name):
        return "subif"
    return "physical"


def _is_backbone_candidate(iface: DeviceInterface) -> bool:
    name = iface.name
    if _SYSTEM_IFACE.search(name):
        return False
    if is_huawei_subinterface(name):
        return False
    if iface.allocated or (iface.used_s_vids and len(iface.used_s_vids) > 0):
        return False
    if _CUSTOMER_HINTS.search(iface.description or ""):
        return False
    kind = _interface_kind(name)
    return kind in {"vlan", "lag", "physical"}


def _score_interface(iface: DeviceInterface, *, prefer_vlan: bool) -> ScoredInterface:
    speed = iface.speed_mbps or 0
    kind = _interface_kind(iface.name)
    score = 0.0
    reasons: list[str] = []

    if not _is_backbone_candidate(iface):
        return ScoredInterface(
            iface.name, speed, iface.oper_status, -1000.0, "不可用", kind, iface.description
        )

    if kind == "vlan":
        score += 200
        reasons.append("VLAN 子接口")
    elif kind == "lag":
        score += 80
        reasons.append("聚合口")
    elif prefer_vlan:
        score -= 120
        reasons.append("物理口")

    score += min(speed / 1000.0, 120.0)
    if speed >= 100_000:
        reasons.append("100G+")
    elif speed >= 25_000:
        reasons.append("25G+")
    elif speed >= 10_000:
        reasons.append("10G+")

    if iface.oper_status == "up":
        score += 25
        reasons.append("在线")
    elif iface.oper_status == "down":
        score -= 20

    desc = iface.description or ""
    if _UPSTREAM_HINTS.search(desc) or _UPSTREAM_HINTS.search(iface.name):
        score += 45
        reasons.append("上联语义")

    parsed_bw = parse_bw_mbps(desc)
    if parsed_bw:
        score += 15
        reasons.append(f"bw({parsed_bw}M)")

    return ScoredInterface(
        name=iface.name,
        speed_mbps=speed,
        oper_status=iface.oper_status,
        score=round(score, 1),
        reason=" · ".join(reasons) if reasons else kind,
        kind=kind,
        description=iface.description,
    )


def _device_interfaces(db: Session, device_id: int) -> list[DeviceInterface]:
    return db.execute(
        select(DeviceInterface)
        .where(DeviceInterface.device_id == device_id)
        .order_by(DeviceInterface.ifindex.asc().nullslast(), DeviceInterface.id.asc())
    ).scalars().all()


def _prefer_vlan_on_device(rows: list[DeviceInterface]) -> bool:
    return any(is_vlan_interface(row.name) for row in rows)


def list_interface_candidates(
    db: Session,
    device_id: int,
    *,
    all_interfaces: bool = False,
    limit: int = 48,
) -> list[ScoredInterface]:
    """Rank device interfaces for backbone link selection.

    When ``all_interfaces`` is true, return every discovered interface (including
  low-score / unavailable rows) for manual operator selection.
    """
    rows = _device_interfaces(db, device_id)
    prefer_vlan = _prefer_vlan_on_device(rows)
    scored = [_score_interface(row, prefer_vlan=prefer_vlan) for row in rows]
    scored.sort(key=lambda row: (-row.score, -row.speed_mbps, row.name))
    if all_interfaces:
        return scored
    scored = [row for row in scored if row.score > 0]
    if prefer_vlan:
        vlan_rows = [row for row in scored if row.kind == "vlan"]
        if vlan_rows:
            return vlan_rows[:limit]
    return scored[:limit]


def rank_interfaces(db: Session, device_id: int, *, limit: int = 48) -> list[ScoredInterface]:
    return list_interface_candidates(db, device_id, all_interfaces=False, limit=limit)


def best_interface(db: Session, device_id: int) -> ScoredInterface | None:
    ranked = rank_interfaces(db, device_id, limit=1)
    return ranked[0] if ranked else None


def _device_priority(device: Device) -> int:
    return _ROLE_PRIORITY.get(device.role, 9)


def _pair_key(a_id: int, z_id: int) -> tuple[int, int]:
    return (min(a_id, z_id), max(a_id, z_id))


def _existing_pairs(db: Session) -> set[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()
    for link in db.execute(select(Link)).scalars().all():
        pairs.add(_pair_key(link.device_a_id, link.device_z_id))
    return pairs


def _link_type(device_a: Device, device_z: Device) -> LinkType:
    if device_a.site_id and device_z.site_id and device_a.site_id != device_z.site_id:
        return LinkType.DCI
    return LinkType.INTRA_DC


def _default_name(device_a: Device, device_z: Device, link_type: LinkType) -> str:
    short_a = device_a.name.split(".")[0][:12]
    short_z = device_z.name.split(".")[0][:12]
    if link_type == LinkType.DCI:
        return f"{short_a}↔{short_z} DCI"
    return f"{short_a}↔{short_z} 站内"


def _interface_description(db: Session, device_id: int, ifname: str) -> str | None:
    if not ifname:
        return None
    iface = db.execute(
        select(DeviceInterface).where(
            DeviceInterface.device_id == device_id,
            DeviceInterface.name == ifname,
        )
    ).scalar_one_or_none()
    return iface.description if iface else None


def _capacity_for_pair(
    db: Session,
    device_a_id: int,
    iface_a: str,
    device_z_id: int,
    iface_z: str,
    *,
    fallback: int = 10_000,
) -> int:
    caps: list[int] = []
    for device_id, ifname in ((device_a_id, iface_a), (device_z_id, iface_z)):
        iface = db.execute(
            select(DeviceInterface).where(
                DeviceInterface.device_id == device_id,
                DeviceInterface.name == ifname,
            )
        ).scalar_one_or_none()
        cap = capacity_from_interface(iface)
        if cap:
            caps.append(cap)
    return min(caps) if caps else fallback


def _resolve_named_interface(
    db: Session,
    device_id: int,
    ifname: str,
) -> ScoredInterface:
    """Honor an operator-specified interface even before SNMP inventory exists."""
    for row in rank_interfaces(db, device_id, limit=50):
        if row.name == ifname:
            return row
    rows = _device_interfaces(db, device_id)
    prefer_vlan = _prefer_vlan_on_device(rows)
    iface = next((row for row in rows if row.name == ifname), None)
    if iface:
        return _score_interface(iface, prefer_vlan=prefer_vlan)
    kind = _interface_kind(ifname)
    return ScoredInterface(ifname, 10_000, "up", 50.0, "手动指定", kind, description=None)


def plan_link(
    db: Session,
    device_a: Device,
    device_z: Device,
    *,
    interface_a: str | None = None,
    interface_z: str | None = None,
) -> dict | None:
    """Pick optimal backbone endpoints between two devices."""
    if device_a.id == device_z.id:
        return None

    if interface_a:
        pick_a = _resolve_named_interface(db, device_a.id, interface_a)
    else:
        pick_a = best_interface(db, device_a.id)
    if interface_z:
        pick_z = _resolve_named_interface(db, device_z.id, interface_z)
    else:
        pick_z = best_interface(db, device_z.id)
    if pick_a is None or pick_z is None:
        return None

    link_type = _link_type(device_a, device_z)
    capacity = _capacity_for_pair(
        db, device_a.id, pick_a.name, device_z.id, pick_z.name,
        fallback=min(pick_a.speed_mbps or 10_000, pick_z.speed_mbps or 10_000) or 10_000,
    )
    site_a = db.get(Site, device_a.site_id) if device_a.site_id else None
    site_z = db.get(Site, device_z.site_id) if device_z.site_id else None
    score = round((pick_a.score + pick_z.score) / 2, 1)

    return {
        "device_a_id": device_a.id,
        "device_z_id": device_z.id,
        "device_a": device_a.name,
        "device_z": device_z.name,
        "site_a": site_a.code if site_a else None,
        "site_z": site_z.code if site_z else None,
        "type": link_type.value,
        "name": _default_name(device_a, device_z, link_type),
        "interface_a": pick_a.name,
        "interface_z": pick_z.name,
        "interface_a_description": pick_a.description or _interface_description(
            db, device_a.id, pick_a.name
        ),
        "interface_z_description": pick_z.description or _interface_description(
            db, device_z.id, pick_z.name
        ),
        "interface_a_score": pick_a.score,
        "interface_z_score": pick_z.score,
        "interface_a_reason": pick_a.reason,
        "interface_z_reason": pick_z.reason,
        "capacity_mbps": capacity,
        "score": score,
        "reason": f"A:{pick_a.reason} · Z:{pick_z.reason}",
    }


def suggest_backbone_links(db: Session) -> list[dict]:
    """Recommend missing backbone links between sites (one optimal pair per site pair)."""
    devices = db.execute(select(Device).order_by(Device.id)).scalars().all()
    if len(devices) < 2:
        return []

    existing = _existing_pairs(db)
    by_site: dict[int | None, list[Device]] = {}
    for device in devices:
        by_site.setdefault(device.site_id, []).append(device)

    site_ids = [sid for sid in by_site if sid is not None]
    suggestions: list[dict] = []

    for i, site_a_id in enumerate(site_ids):
        for site_z_id in site_ids[i + 1 :]:
            candidates: list[dict] = []
            for device_a in by_site[site_a_id]:
                for device_z in by_site[site_z_id]:
                    if _pair_key(device_a.id, device_z.id) in existing:
                        continue
                    plan = plan_link(db, device_a, device_z)
                    if plan:
                        plan["priority"] = _device_priority(device_a) + _device_priority(device_z)
                        candidates.append(plan)
            if not candidates:
                continue
            candidates.sort(
                key=lambda row: (
                    row["priority"],
                    -row["score"],
                    -row["capacity_mbps"],
                )
            )
            best = candidates[0]
            best["recommended"] = True
            suggestions.append(best)

    for site_id, members in by_site.items():
        if site_id is None or len(members) < 2:
            continue
        members = sorted(members, key=lambda d: (_device_priority(d), d.id))
        uplink_roles = {DeviceRole.DCI_GW, DeviceRole.BORDER_LEAF, DeviceRole.SPINE, DeviceRole.PE}
        cores = [d for d in members if d.role in uplink_roles]
        access = [d for d in members if d.role not in uplink_roles]
        if not cores or not access:
            continue
        device_a, device_z = cores[0], access[0]
        if _pair_key(device_a.id, device_z.id) in existing:
            continue
        plan = plan_link(db, device_a, device_z)
        if plan:
            plan["recommended"] = True
            suggestions.append(plan)

    suggestions.sort(key=lambda row: (-row.get("score", 0), row["name"]))
    return suggestions


def resolve_link_payload(db: Session, payload: dict) -> dict:
    """Fill missing interfaces/capacity/name on a link create payload."""
    device_a = db.get(Device, payload["device_a_id"])
    device_z = db.get(Device, payload["device_z_id"])
    if not device_a or not device_z:
        raise ValueError("设备不存在")

    plan = plan_link(
        db,
        device_a,
        device_z,
        interface_a=payload.get("interface_a"),
        interface_z=payload.get("interface_z"),
    )
    if not plan:
        raise ValueError("未找到可用 VLAN 子接口/上联口，请先执行 SNMP 发现或现网学习")

    out = dict(payload)
    out.setdefault("name", plan["name"])
    out.setdefault("type", plan["type"])
    out.setdefault("interface_a", plan["interface_a"])
    out.setdefault("interface_z", plan["interface_z"])
    out.setdefault("capacity_mbps", plan["capacity_mbps"])
    return out
