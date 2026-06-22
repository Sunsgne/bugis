"""Load IGP backbone interface costs from learned device configs."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.device_learn_run import DeviceLearnRun
from app.models.enums import Vendor
from app.models.link import Link
from app.services import config_learn_parse, config_mgmt

DEFAULT_IGP_COST = 10


def _normalize_iface(name: str) -> str:
    return name.strip().lower().replace(" ", "")


def _inventory_backbone_map(inventory: dict) -> dict[str, dict]:
    """Normalized interface name → backbone IGP entry (enable + cost)."""
    out: dict[str, dict] = {}
    for raw in inventory.get("igp_costs") or inventory.get("backbone_interfaces") or []:
        if raw.get("backbone") is False:
            continue
        iface = str(raw.get("interface") or "").strip()
        cost = raw.get("cost")
        if not iface or cost is None:
            continue
        out[_normalize_iface(iface)] = raw
    return out


def _latest_inventory_dict(db: Session, device_id: int) -> dict | None:
    run = db.execute(
        select(DeviceLearnRun)
        .where(
            DeviceLearnRun.device_id == device_id,
            DeviceLearnRun.status == "success",
        )
        .order_by(DeviceLearnRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if run and run.inventory:
        return run.inventory
    snap = config_mgmt.latest_learned(db, device_id)
    if not snap or not snap.content:
        return None
    device = db.get(Device, device_id)
    if not device:
        return None
    return config_learn_parse.parse_inventory(snap.content, device.vendor).as_dict()


def device_backbone_interfaces(db: Session, device_id: int) -> dict[str, dict]:
    """Return normalized interface name → backbone IGP metadata."""
    inv = _latest_inventory_dict(db, device_id)
    if not inv:
        return {}
    return _inventory_backbone_map(inv)


def device_igp_costs(db: Session, device_id: int) -> dict[str, int]:
    """Return normalized interface name → IGP cost (backbone interfaces only)."""
    return {
        k: int(v["cost"])
        for k, v in device_backbone_interfaces(db, device_id).items()
        if v.get("cost") is not None
    }


def device_igp_protocol(db: Session, device_id: int) -> str | None:
    inv = _latest_inventory_dict(db, device_id)
    if not inv:
        return None
    return inv.get("igp_protocol")


def lookup_backbone_interface(
    backbone: dict[str, dict],
    interface: str | None,
) -> dict | None:
    if not interface:
        return None
    return backbone.get(_normalize_iface(interface))


def lookup_interface_cost(
    costs: dict[str, int],
    interface: str | None,
    *,
    default: int = DEFAULT_IGP_COST,
) -> tuple[int, bool]:
    """Return (cost, learned) for a backbone interface name."""
    if not interface:
        return default, False
    key = _normalize_iface(interface)
    if key in costs:
        return costs[key], True
    return default, False


def link_transit_cost(
    db: Session,
    link: Link,
    from_device_id: int,
    *,
    cost_cache: dict[int, dict[str, int]] | None = None,
) -> tuple[int, str | None, bool]:
    """Outbound IGP cost when traversing *link* leaving *from_device_id*."""
    if from_device_id == link.device_a_id:
        egress_iface = link.interface_a
    elif from_device_id == link.device_z_id:
        egress_iface = link.interface_z
    else:
        return DEFAULT_IGP_COST, None, False

    cache = cost_cache
    if cache is None:
        cache = {
            link.device_a_id: device_igp_costs(db, link.device_a_id),
            link.device_z_id: device_igp_costs(db, link.device_z_id),
        }
    costs = cache.get(from_device_id) or device_igp_costs(db, from_device_id)
    cost, learned = lookup_interface_cost(costs, egress_iface)
    return cost, egress_iface, learned


def link_backbone_igp(
    db: Session,
    link: Link,
    *,
    backbone_cache: dict[int, dict[str, dict]] | None = None,
) -> dict:
    """Per-end IGP backbone metadata for a platform Link row."""

    def _side(device_id: int, iface: str | None) -> dict:
        if backbone_cache is None:
            bb = device_backbone_interfaces(db, device_id)
        else:
            bb = backbone_cache.get(device_id) or device_backbone_interfaces(db, device_id)
        entry = lookup_backbone_interface(bb, iface)
        if not entry:
            return {
                "interface": iface,
                "backbone": False,
                "igp_cost": None,
                "igp_process": None,
                "protocol": None,
            }
        return {
            "interface": iface,
            "backbone": True,
            "igp_cost": entry.get("cost"),
            "igp_process": entry.get("igp_process"),
            "protocol": entry.get("protocol"),
        }

    a = _side(link.device_a_id, link.interface_a)
    z = _side(link.device_z_id, link.interface_z)
    return {
        "igp_a": a,
        "igp_z": z,
        "backbone_link": a["backbone"] and z["backbone"],
        "igp_cost_a": a["igp_cost"],
        "igp_cost_z": z["igp_cost"],
        "igp_process_a": a["igp_process"],
        "igp_process_z": z["igp_process"],
    }


def build_cost_cache(db: Session, device_ids: set[int]) -> dict[int, dict[str, int]]:
    return {did: device_igp_costs(db, did) for did in device_ids}


def build_backbone_cache(db: Session, device_ids: set[int]) -> dict[int, dict[str, dict]]:
    return {did: device_backbone_interfaces(db, did) for did in device_ids}
