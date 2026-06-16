"""Overlay identifier inventory: VNI / VSI / RD from platform + live network.

Mirrors the port_inventory pattern for S-VID: merge platform circuits with
learned running-config so new provisioning avoids colliding with on-box services.
Scanning is read-only and never pushes configuration to devices.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit
from app.models.controlplane import VtepPeer
from app.models.device import Device
from app.models.device_learn_run import DeviceLearnRun
from app.services import config_learn_parse, config_mgmt


@dataclass
class OverlayServiceEntry:
    device_id: int
    device_name: str
    vendor: str
    service_name: str
    vni: int | None = None
    rd: str | None = None
    rt: str | None = None
    interfaces: list[str] = field(default_factory=list)
    vlans: list[int] = field(default_factory=list)
    source: str = "network"  # platform | network | controller
    circuit_id: int | None = None
    circuit_code: str | None = None
    circuit_name: str | None = None

    def as_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "device": self.device_name,
            "vendor": self.vendor,
            "service_name": self.service_name,
            "vsi_name": self.service_name,
            "vni": self.vni,
            "rd": self.rd,
            "rt": self.rt,
            "interfaces": self.interfaces,
            "vlans": self.vlans,
            "source": self.source,
            "circuit_id": self.circuit_id,
            "circuit_code": self.circuit_code,
            "circuit_name": self.circuit_name,
            "reserved": True,
        }


def _platform_circuits(db: Session) -> list[Circuit]:
    return db.execute(select(Circuit).where(Circuit.vni.is_not(None))).scalars().all()


def _circuit_by_vni(db: Session) -> dict[int, Circuit]:
    return {c.vni: c for c in _platform_circuits(db) if c.vni is not None}


def _circuit_by_vsi(db: Session) -> dict[str, Circuit]:
    out: dict[str, Circuit] = {}
    for c in db.execute(select(Circuit).where(Circuit.vsi_name.is_not(None))).scalars():
        if c.vsi_name:
            out[c.vsi_name] = c
    return out


def _latest_learn_inventory(db: Session, device_id: int) -> dict | None:
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
    inv = config_learn_parse.parse_inventory(snap.content, device.vendor)
    return inv.as_dict()


def _entries_from_inventory(
    db: Session,
    device: Device,
    inventory: dict,
    *,
    by_vni: dict[int, Circuit],
    by_vsi: dict[str, Circuit],
) -> list[OverlayServiceEntry]:
    entries: list[OverlayServiceEntry] = []
    for raw in inventory.get("l2_services") or []:
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        vni = raw.get("vni")
        circuit = by_vni.get(vni) if vni is not None else None
        if circuit is None and name in by_vsi:
            circuit = by_vsi[name]
        source = "platform" if circuit else "network"
        entries.append(
            OverlayServiceEntry(
                device_id=device.id,
                device_name=device.name,
                vendor=device.vendor.value,
                service_name=name,
                vni=vni,
                rd=raw.get("rd"),
                rt=raw.get("rt"),
                interfaces=list(raw.get("interfaces") or []),
                vlans=list(raw.get("vlans") or []),
                source=source,
                circuit_id=circuit.id if circuit else None,
                circuit_code=circuit.code if circuit else None,
                circuit_name=circuit.name if circuit else None,
            )
        )
    return entries


def device_overlay_inventory(db: Session, device: Device) -> dict:
    """Overlay services discovered on one device (read-only)."""
    inventory = _latest_learn_inventory(db, device.id)
    by_vni = _circuit_by_vni(db)
    by_vsi = _circuit_by_vsi(db)
    items: list[OverlayServiceEntry] = []
    if inventory:
        items.extend(
            _entries_from_inventory(db, device, inventory, by_vni=by_vni, by_vsi=by_vsi)
        )

    # Platform circuits on this device without learned match still reserve VNI/VSI.
    from app.models.circuit import CircuitEndpoint

    for ep, circuit in db.execute(
        select(CircuitEndpoint, Circuit)
        .join(Circuit, Circuit.id == CircuitEndpoint.circuit_id)
        .where(CircuitEndpoint.device_id == device.id, Circuit.vni.is_not(None))
    ).all():
        vsi = circuit.vsi_name or f"vsi_{circuit.code.replace('-', '_').lower()}"
        if any(e.circuit_id == circuit.id for e in items):
            continue
        items.append(
            OverlayServiceEntry(
                device_id=device.id,
                device_name=device.name,
                vendor=device.vendor.value,
                service_name=vsi,
                vni=circuit.vni,
                rd=circuit.route_distinguisher,
                rt=circuit.route_target,
                interfaces=[ep.interface_name],
                source="platform",
                circuit_id=circuit.id,
                circuit_code=circuit.code,
                circuit_name=circuit.name,
            )
        )

    vnis = sorted({e.vni for e in items if e.vni is not None})
    network_only = [e for e in items if e.source == "network"]
    return {
        "device_id": device.id,
        "device": device.name,
        "vendor": device.vendor.value,
        "has_learned_config": inventory is not None,
        "service_count": len(items),
        "network_only_count": len(network_only),
        "platform_count": len(items) - len(network_only),
        "vnis": vnis,
        "items": [e.as_dict() for e in items],
    }


def fleet_overlay_inventory(db: Session) -> dict:
    """Aggregate overlay inventory across all devices (read-only scan)."""
    devices = db.execute(select(Device).order_by(Device.id)).scalars().all()
    by_vni = _circuit_by_vni(db)
    by_vsi = _circuit_by_vsi(db)

    all_items: list[OverlayServiceEntry] = []
    devices_scanned = 0
    devices_with_data = 0

    for device in devices:
        inventory = _latest_learn_inventory(db, device.id)
        if inventory:
            devices_with_data += 1
            all_items.extend(
                _entries_from_inventory(
                    db, device, inventory, by_vni=by_vni, by_vsi=by_vsi
                )
            )
        devices_scanned += 1

    # Controller VTEP VNIs (platform-provisioned state).
    controller_vnis: set[int] = set()
    for peer in db.execute(select(VtepPeer)).scalars().all():
        for part in (peer.vnis or "").split(","):
            part = part.strip()
            if part.isdigit():
                controller_vnis.add(int(part))

    reserved_vnis = network_reserved_vnis(db, items=all_items)
    reserved_vsis = network_reserved_vsis(db, items=all_items)

    network_items = [e for e in all_items if e.source == "network"]
    platform_items = [e for e in all_items if e.source == "platform"]

    return {
        "devices_scanned": devices_scanned,
        "devices_with_inventory": devices_with_data,
        "total_services": len(all_items),
        "platform_services": len(platform_items),
        "network_only_services": len(network_items),
        "reserved_vni_count": len(reserved_vnis),
        "reserved_vsi_count": len(reserved_vsis),
        "controller_vnis": sorted(controller_vnis),
        "smart_allocation_enabled": _smart_allocation_enabled(),
        "items": [e.as_dict() for e in all_items],
        "reserved_vnis": sorted(reserved_vnis),
        "reserved_vsis": sorted(reserved_vsis),
    }


def scan_fleet_overlay(db: Session) -> dict:
    """Read-only fleet scan from latest learned configs (no device push)."""
    return fleet_overlay_inventory(db)


def _smart_allocation_enabled() -> bool:
    from app.core.config import settings

    return bool(getattr(settings, "smart_overlay_allocation", True))


def network_reserved_vnis(
    db: Session,
    *,
    items: list[OverlayServiceEntry] | None = None,
) -> set[int]:
    """VNIs that must not be auto-allocated (platform + on-box)."""
    reserved = {c.vni for c in _platform_circuits(db) if c.vni is not None}
    if items is None:
        by_vni = _circuit_by_vni(db)
        by_vsi = _circuit_by_vsi(db)
        for device in db.execute(select(Device)).scalars().all():
            inventory = _latest_learn_inventory(db, device.id)
            if not inventory:
                continue
            for entry in _entries_from_inventory(
                db, device, inventory, by_vni=by_vni, by_vsi=by_vsi
            ):
                if entry.vni is not None:
                    reserved.add(entry.vni)
    else:
        for entry in items:
            if entry.vni is not None:
                reserved.add(entry.vni)
    for peer in db.execute(select(VtepPeer)).scalars().all():
        for part in (peer.vnis or "").split(","):
            if part.strip().isdigit():
                reserved.add(int(part.strip()))
    return reserved


def network_reserved_vsis(
    db: Session,
    *,
    items: list[OverlayServiceEntry] | None = None,
) -> set[str]:
    """VSI / service names that must not be auto-allocated."""
    reserved = set(_circuit_by_vsi(db).keys())
    if items is None:
        by_vni = _circuit_by_vni(db)
        by_vsi = _circuit_by_vsi(db)
        for device in db.execute(select(Device)).scalars().all():
            inventory = _latest_learn_inventory(db, device.id)
            if not inventory:
                continue
            for entry in _entries_from_inventory(
                db, device, inventory, by_vni=by_vni, by_vsi=by_vsi
            ):
                if entry.service_name:
                    reserved.add(entry.service_name)
    else:
        for entry in items:
            if entry.service_name:
                reserved.add(entry.service_name)
    return reserved


def vni_conflict_on_network(
    db: Session,
    vni: int,
    *,
    exclude_circuit_id: int | None = None,
) -> dict | None:
    """Return first network conflict detail for a VNI, if any."""
    by_vni = _circuit_by_vni(db)
    circuit = by_vni.get(vni)
    if circuit and circuit.id != exclude_circuit_id:
        return {
            "type": "platform",
            "circuit_code": circuit.code,
            "message": f"VNI {vni} 已被平台专线 {circuit.code} 占用",
        }

    for raw in fleet_overlay_inventory(db).get("items") or []:
        if raw.get("vni") != vni:
            continue
        if raw.get("source") == "network":
            return {
                "type": "network",
                "device": raw.get("device"),
                "service_name": raw.get("service_name"),
                "message": (
                    f"VNI {vni} 已在现网设备 {raw.get('device')} "
                    f"的服务 {raw.get('service_name')} 中使用（未纳管）"
                ),
            }
    return None


def vsi_conflict_on_network(
    db: Session,
    vsi_name: str,
    *,
    exclude_circuit_id: int | None = None,
) -> dict | None:
    by_vsi = _circuit_by_vsi(db)
    circuit = by_vsi.get(vsi_name)
    if circuit and circuit.id != exclude_circuit_id:
        return {
            "type": "platform",
            "circuit_code": circuit.code,
            "message": f"VSI {vsi_name} 已被平台专线 {circuit.code} 占用",
        }

    for raw in fleet_overlay_inventory(db).get("items") or []:
        name = raw.get("service_name") or raw.get("vsi_name")
        if name != vsi_name:
            continue
        if raw.get("source") == "network":
            return {
                "type": "network",
                "device": raw.get("device"),
                "message": (
                    f"VSI {vsi_name} 已在现网设备 {raw.get('device')} 中使用（未纳管）"
                ),
            }
    return None


def overlay_warnings_for_circuit(db: Session, circuit: Circuit) -> list[dict]:
    """Non-blocking warnings for manual VNI/VSI that collide with live network."""
    warnings: list[dict] = []
    if circuit.vni is not None:
        hit = vni_conflict_on_network(db, circuit.vni, exclude_circuit_id=circuit.id)
        if hit and hit.get("type") == "network":
            warnings.append({
                "level": "warning",
                "code": "vni_network_in_use",
                "message": hit["message"],
            })
    if circuit.vsi_name:
        hit = vsi_conflict_on_network(
            db, circuit.vsi_name, exclude_circuit_id=circuit.id
        )
        if hit and hit.get("type") == "network":
            warnings.append({
                "level": "warning",
                "code": "vsi_network_in_use",
                "message": hit["message"],
            })
    return warnings
