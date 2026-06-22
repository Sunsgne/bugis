"""Load IGP interface costs from learned device configs for underlay path weighting."""
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


def _inventory_igp_map(inventory: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for raw in inventory.get("igp_costs") or []:
        iface = str(raw.get("interface") or "").strip()
        cost = raw.get("cost")
        if not iface or cost is None:
            continue
        out[_normalize_iface(iface)] = int(cost)
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


def device_igp_costs(db: Session, device_id: int) -> dict[str, int]:
    """Return normalized interface name → IGP cost for a device."""
    inv = _latest_inventory_dict(db, device_id)
    if not inv:
        return {}
    return _inventory_igp_map(inv)


def device_igp_protocol(db: Session, device_id: int) -> str | None:
    inv = _latest_inventory_dict(db, device_id)
    if not inv:
        return None
    return inv.get("igp_protocol")


def lookup_interface_cost(
    costs: dict[str, int],
    interface: str | None,
    *,
    default: int = DEFAULT_IGP_COST,
) -> tuple[int, bool]:
    """Return (cost, learned) for an interface name."""
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


def build_cost_cache(db: Session, device_ids: set[int]) -> dict[int, dict[str, int]]:
    return {did: device_igp_costs(db, did) for did in device_ids}
