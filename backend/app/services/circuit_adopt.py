"""Adopt existing on-box S-VID bindings into platform inventory without config push."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit, CircuitEndpoint
from app.models.device import Device
from app.models.enums import AccessMode, CircuitStatus, ServiceType
from app.models.tenant import Tenant
from app.schemas.circuit import (
    CircuitAdoptBinding,
    CircuitAdoptCreate,
    CircuitAdoptVniCreate,
    CircuitEndpointCreate,
)
from app.services import allocation, concurrent_scan, port_inventory, validation
from app.services import igp_cost_service
from app.controller import controller as bugis_controller


def _endpoint_tuple(
    device_id: int,
    interface_name: str,
    access_mode: AccessMode | str,
    vlan_id: int | None,
    inner_vlan_id: int | None,
) -> tuple:
    mode = access_mode.value if isinstance(access_mode, AccessMode) else access_mode
    return (
        device_id,
        port_inventory._normalize_iface(interface_name),
        mode,
        vlan_id,
        inner_vlan_id,
    )


def validate_adopted_endpoints_replace(
    db: Session,
    circuit: Circuit,
    endpoints: list[CircuitEndpointCreate],
) -> dict[int, dict]:
    """Validate endpoint replacement for an adopted circuit.

    Existing endpoints may be kept as-is; new or changed endpoints must match
    adoptable on-box bindings and share the circuit VNI/VSI. Returns payload
    index -> binding row for newly adopted endpoints.
    """
    existing_keys: set[tuple] = set()
    for ep in circuit.endpoints:
        mode = ep.access_mode or AccessMode.DOT1Q
        svid = ep.vlan_id or circuit.vlan_id
        existing_keys.add(
            _endpoint_tuple(ep.device_id, ep.interface_name, mode, svid, ep.inner_vlan_id)
        )

    adopt_rows: dict[int, dict] = {}
    for idx, ep in enumerate(endpoints):
        mode = ep.access_mode or AccessMode.DOT1Q
        svid = ep.vlan_id or circuit.vlan_id
        key = _endpoint_tuple(ep.device_id, ep.interface_name, mode, svid, ep.inner_vlan_id)
        if key in existing_keys:
            continue

        device = db.get(Device, ep.device_id)
        if not device:
            raise HTTPException(status_code=404, detail=f"device {ep.device_id} not found")

        row = find_adoptable_binding(
            db,
            device,
            interface_name=ep.interface_name,
            access_mode=mode,
            vlan_id=svid,
            inner_vlan_id=ep.inner_vlan_id,
            for_circuit_id=circuit.id,
        )
        if not row:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{ep.interface_name} 上未发现可纳管的现网绑定 "
                    f"({mode.value}{f' vlan={svid}' if svid else ''})"
                ),
            )

        row_vni = row.get("vni")
        if circuit.vni is not None and row_vni is not None and int(row_vni) != circuit.vni:
            raise HTTPException(
                status_code=409,
                detail=f"端点 VNI {row_vni} 与专线 VNI {circuit.vni} 不一致",
            )
        row_vsi = row.get("vsi_name")
        if circuit.vsi_name and row_vsi:
            norm_row = allocation.normalize_vsi_name(str(row_vsi))
            if norm_row != circuit.vsi_name:
                raise HTTPException(
                    status_code=409,
                    detail=f"端点 VSI {row_vsi} 与专线 VSI {circuit.vsi_name} 不一致",
                )

        adopt_rows[idx] = row

    return adopt_rows


def _binding_key(
    iface: str,
    mode: str,
    svid: int | None,
    cvid: int | None,
) -> tuple:
    return (port_inventory._normalize_iface(iface), mode, svid, cvid)


def _coerce_access_mode(mode: str | None) -> AccessMode:
    if not mode:
        return AccessMode.DOT1Q
    try:
        return AccessMode(mode)
    except ValueError:
        return AccessMode.DOT1Q


def _endpoint_selection_key(
    device_id: int,
    interface_name: str,
    access_mode: AccessMode | str,
    vlan_id: int | None,
    inner_vlan_id: int | None,
) -> str:
    mode = access_mode.value if isinstance(access_mode, AccessMode) else access_mode
    return (
        f"{device_id}:{port_inventory._normalize_iface(interface_name)}:"
        f"{mode}:{vlan_id or ''}:{inner_vlan_id or ''}"
    )


def _endpoint_labels(count: int) -> list[str]:
    if count <= 0:
        return []
    if count == 1:
        return ["A"]
    if count == 2:
        return ["A", "Z"]
    return [chr(ord("A") + i) for i in range(count)]


def _devices_for_vni_scan(db: Session, device_ids: list[int] | None) -> list[Device]:
    stmt = select(Device).order_by(Device.id)
    if device_ids:
        stmt = stmt.where(Device.id.in_(device_ids))
    return list(db.execute(stmt).scalars().all())


def _l2_service_for_vni(inventory: dict, vni: int) -> dict | None:
    for raw in inventory.get("l2_services") or []:
        if raw.get("vni") == vni:
            return raw
    return None


def _l2_service_names(inventory: dict) -> dict[str, dict]:
    """Map VSI/BD aliases (incl. Huawei bd_N) onto l2_service rows."""
    out: dict[str, dict] = {}
    for raw in inventory.get("l2_services") or []:
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        out[name] = raw
        if name.startswith("bd_"):
            out.setdefault(name[3:], raw)
    return out


def _service_name_matches(link_name: str, service_name: str | None) -> bool:
    if not link_name or not service_name:
        return False
    link = str(link_name).strip()
    svc = str(service_name).strip()
    if link == svc:
        return True
    if svc.startswith("bd_") and link == svc[3:]:
        return True
    if link.startswith("bd_") and svc == link[3:]:
        return True
    return False


def _binding_vni(raw: dict, inventory: dict) -> int | None:
    raw_vni = raw.get("vni")
    if raw_vni is not None:
        return int(raw_vni)

    l2_by_name = _l2_service_names(inventory)
    for key in ("vsi_name", "bridge_domain"):
        link = raw.get(key)
        if not link:
            continue
        svc = l2_by_name.get(str(link))
        if svc and svc.get("vni") is not None:
            return int(svc["vni"])
    return None


def _binding_matches_vni(raw: dict, vni: int, inventory: dict) -> bool:
    """True when an access binding belongs to the target EVPN VNI."""
    target = int(vni)
    resolved = _binding_vni(raw, inventory)
    if resolved == target:
        return True

    link_names = [
        str(raw[key]).strip()
        for key in ("vsi_name", "bridge_domain")
        if raw.get(key)
    ]
    l2_svc = _l2_service_for_vni(inventory, target)
    if l2_svc:
        svc_name = l2_svc.get("name")
        if any(_service_name_matches(name, svc_name) for name in link_names):
            return True
        iface = str(raw.get("interface") or "").strip()
        if iface and iface in (l2_svc.get("interfaces") or []):
            return True

    return False


def _interface_name_candidates(db: Session, device: Device, interface_name: str) -> list[str]:
    canonical = port_inventory.resolve_interface_name(db, device, interface_name)
    names: list[str] = []
    for candidate in (canonical, interface_name):
        norm = port_inventory._normalize_iface(candidate)
        if norm and norm not in names:
            names.append(norm)
    return names


def _adoptability_reason(
    db: Session,
    device: Device,
    *,
    interface_name: str,
    access_mode: AccessMode,
    vlan_id: int | None,
    inner_vlan_id: int | None,
) -> str:
    bindings = port_inventory.list_port_bindings(db, device)
    mode = access_mode.value
    keys = {
        _binding_key(name, mode, vlan_id, inner_vlan_id)
        for name in _interface_name_candidates(db, device, interface_name)
    }
    for item in bindings.get("items") or []:
        item_key = _binding_key(
            item["interface_name"],
            item.get("access_mode") or "dot1q",
            item.get("s_vid"),
            item.get("c_vid"),
        )
        if item_key not in keys:
            continue
        if item.get("circuit_id"):
            code = item.get("circuit_code") or item.get("circuit_id")
            return f"已被专线 {code} 纳管"
        if item.get("binding_type") == "platform":
            return "已被平台端点占用"
        return "现网绑定状态不可纳管"
    return "未发现可纳管的现网绑定（请先执行现网学习）"


def _append_vni_endpoint_candidate(
    db: Session,
    device: Device,
    *,
    vni: int,
    inventory: dict,
    raw: dict,
    l2_svc: dict | None,
    seen: set[tuple],
    results: list[dict],
) -> None:
    iface = str(raw.get("interface") or "").strip()
    if not iface:
        return
    if not _binding_matches_vni(raw, vni, inventory):
        return

    mode = _coerce_access_mode(raw.get("access_mode"))
    svid = raw.get("s_vid")
    cvid = raw.get("c_vid")
    canonical_iface = port_inventory.resolve_interface_name(db, device, iface)
    dedup_key = (
        device.id,
        port_inventory._normalize_iface(canonical_iface),
        mode.value,
        svid,
        cvid,
    )
    if dedup_key in seen:
        return
    seen.add(dedup_key)

    row = find_adoptable_binding(
        db,
        device,
        interface_name=iface,
        access_mode=mode,
        vlan_id=svid,
        inner_vlan_id=cvid,
    )
    adoptable = row is not None
    reason = None if adoptable else _adoptability_reason(
        db,
        device,
        interface_name=iface,
        access_mode=mode,
        vlan_id=svid,
        inner_vlan_id=cvid,
    )

    vsi_name = raw.get("vsi_name") or raw.get("bridge_domain")
    if not vsi_name and l2_svc:
        vsi_name = l2_svc.get("name")

    results.append({
        "key": _endpoint_selection_key(device.id, canonical_iface, mode, svid, cvid),
        "device_id": device.id,
        "device_name": device.name,
        "interface_name": port_inventory._normalize_iface(canonical_iface),
        "access_mode": mode.value,
        "vlan_id": svid,
        "inner_vlan_id": cvid,
        "vni": int(vni),
        "vsi_name": vsi_name,
        "description": raw.get("description"),
        "rd": raw.get("rd") or (l2_svc.get("rd") if l2_svc else None),
        "rt": raw.get("rt") or (l2_svc.get("rt") if l2_svc else None),
        "adoptable": adoptable,
        "reason": reason,
    })


def find_adoptable_endpoints_by_vni(
    db: Session,
    vni: int,
    *,
    device_ids: list[int] | None = None,
    refresh_inventory: bool = False,
) -> list[dict]:
    """Discover access bindings for a VNI across learned device inventories."""
    devices = _devices_for_vni_scan(db, device_ids)
    if refresh_inventory and devices:
        concurrent_scan.scan_devices_parallel(
            [d.id for d in devices], include_legacy=False
        )
        for dev in devices:
            db.refresh(dev)

    results: list[dict] = []
    seen: set[tuple] = set()

    for device in devices:
        inventory = igp_cost_service._latest_inventory_dict(db, device.id)
        if not inventory:
            continue
        l2_svc = _l2_service_for_vni(inventory, vni)
        bindings_by_iface = {
            str(raw.get("interface") or "").strip(): raw
            for raw in inventory.get("access_bindings") or []
        }
        for raw in inventory.get("access_bindings") or []:
            _append_vni_endpoint_candidate(
                db,
                device,
                vni=vni,
                inventory=inventory,
                raw=raw,
                l2_svc=l2_svc,
                seen=seen,
                results=results,
            )

        if l2_svc:
            for iface in l2_svc.get("interfaces") or []:
                iface = str(iface).strip()
                if not iface:
                    continue
                raw = bindings_by_iface.get(iface)
                if raw:
                    continue
                vlans = l2_svc.get("vlans") or [None]
                for svid in vlans:
                    synthetic = {
                        "interface": iface,
                        "access_mode": "dot1q",
                        "s_vid": svid,
                        "vsi_name": l2_svc.get("name"),
                        "vni": vni,
                    }
                    _append_vni_endpoint_candidate(
                        db,
                        device,
                        vni=vni,
                        inventory=inventory,
                        raw=synthetic,
                        l2_svc=l2_svc,
                        seen=seen,
                        results=results,
                    )

    results.sort(
        key=lambda row: (row["device_name"], row["interface_name"], row.get("vlan_id") or 0)
    )
    return results


def preview_adopt_by_vni(
    db: Session,
    vni: int,
    *,
    device_ids: list[int] | None = None,
    refresh_inventory: bool = False,
) -> dict:
    if not (validation.VNI_MIN <= vni <= validation.VNI_MAX):
        raise HTTPException(status_code=400, detail=f"VNI {vni} 超出有效范围")

    endpoints = find_adoptable_endpoints_by_vni(
        db,
        vni,
        device_ids=device_ids,
        refresh_inventory=refresh_inventory,
    )
    adoptable = [row for row in endpoints if row["adoptable"]]

    vsi_name: str | None = None
    rd: str | None = None
    rt: str | None = None
    for ep in endpoints:
        if ep.get("vsi_name") and not vsi_name:
            vsi_name = str(ep["vsi_name"])
        if ep.get("rd") and not rd:
            rd = ep["rd"]
        if ep.get("rt") and not rt:
            rt = ep["rt"]

    existing = db.execute(select(Circuit).where(Circuit.vni == vni).limit(1)).scalar_one_or_none()
    conflict_msg = allocation.vni_unavailable_message(db, vni, for_adopt=True)

    return {
        "vni": vni,
        "vsi_name": allocation.normalize_vsi_name(vsi_name) if vsi_name else None,
        "rd": rd,
        "rt": rt,
        "endpoints": endpoints,
        "adoptable_count": len(adoptable),
        "total_count": len(endpoints),
        "existing_circuit_id": existing.id if existing else None,
        "existing_circuit_code": existing.code if existing else None,
        "existing_circuit_adopted": existing.adopted if existing else None,
        "conflict_message": conflict_msg,
        "can_adopt": bool(adoptable) and conflict_msg is None,
    }


def adopt_circuit_from_vni(
    db: Session,
    payload: CircuitAdoptVniCreate,
    *,
    created_by: str | None = None,
) -> Circuit:
    """Register all discovered access bindings for a VNI as one adopted circuit."""
    if not (validation.VNI_MIN <= payload.vni <= validation.VNI_MAX):
        raise HTTPException(status_code=400, detail=f"VNI {payload.vni} 超出有效范围")

    msg = allocation.vni_unavailable_message(db, payload.vni, for_adopt=True)
    if msg:
        raise HTTPException(status_code=409, detail=msg)

    endpoints = find_adoptable_endpoints_by_vni(
        db,
        payload.vni,
        device_ids=payload.device_ids,
        refresh_inventory=payload.refresh_inventory,
    )
    adoptable = [row for row in endpoints if row["adoptable"]]
    if payload.endpoint_keys:
        allowed = set(payload.endpoint_keys)
        adoptable = [row for row in adoptable if row["key"] in allowed]
    if not adoptable:
        raise HTTPException(
            status_code=409,
            detail=f"VNI {payload.vni} 未发现可纳管的接入端点，请先执行现网学习",
        )

    labels = _endpoint_labels(len(adoptable))
    bindings = [
        CircuitAdoptBinding(
            device_id=ep["device_id"],
            label=labels[i],
            interface_name=ep["interface_name"],
            access_mode=_coerce_access_mode(ep["access_mode"]),
            vlan_id=ep.get("vlan_id"),
            inner_vlan_id=ep.get("inner_vlan_id"),
        )
        for i, ep in enumerate(adoptable)
    ]

    vsi = payload.vsi_name
    if not vsi:
        for ep in adoptable:
            if ep.get("vsi_name"):
                vsi = allocation.normalize_vsi_name(str(ep["vsi_name"]))
                break

    adopt_payload = CircuitAdoptCreate(
        name=payload.name,
        tenant_id=payload.tenant_id,
        service_type=payload.service_type,
        bindings=bindings,
        vni=payload.vni,
        vsi_name=vsi,
        vlan_id=payload.vlan_id,
        bandwidth_mbps=payload.bandwidth_mbps,
        description=payload.description or "现网纳管（按 VNI · 不下发配置）",
        refresh_inventory=False,
    )
    return adopt_circuit_from_inventory(db, adopt_payload, created_by=created_by)


def find_adoptable_binding(
    db: Session,
    device: Device,
    *,
    interface_name: str,
    access_mode: AccessMode,
    vlan_id: int | None,
    inner_vlan_id: int | None = None,
    for_circuit_id: int | None = None,
) -> dict | None:
    """Return port-binding row if it exists on-box and is not yet platform-managed.

    When ``for_circuit_id`` is set (extending an adopted circuit), bindings already
    associated with that circuit via VNI catalog inference are still adoptable.
    """
    bindings = port_inventory.list_port_bindings(db, device)
    mode = access_mode.value
    keys = {
        _binding_key(name, mode, vlan_id, inner_vlan_id)
        for name in _interface_name_candidates(db, device, interface_name)
    }
    for row in bindings.get("items") or []:
        row_key = _binding_key(
            row["interface_name"],
            row.get("access_mode") or "dot1q",
            row.get("s_vid"),
            row.get("c_vid"),
        )
        if row_key not in keys:
            continue
        circuit_id = row.get("circuit_id")
        if circuit_id:
            if not (for_circuit_id and circuit_id == for_circuit_id):
                return None
        if row.get("binding_type") == "platform" and not for_circuit_id:
            return None
        if row.get("binding_type") == "platform" and for_circuit_id:
            if circuit_id != for_circuit_id:
                return None
        return row
    return None


def adopt_circuit_from_inventory(
    db: Session,
    payload: CircuitAdoptCreate,
    *,
    created_by: str | None = None,
) -> Circuit:
    """Register discovered S-VID service(s) as ACTIVE adopted circuits — no device push."""
    if not payload.bindings:
        raise HTTPException(status_code=400, detail="至少选择一个现网绑定")

    tenant = db.get(Tenant, payload.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant not found")

    device_ids = list({b.device_id for b in payload.bindings})
    devices: dict[int, Device] = {}
    for did in device_ids:
        dev = db.get(Device, did)
        if not dev:
            raise HTTPException(status_code=404, detail=f"device {did} not found")
        devices[did] = dev

    if payload.refresh_inventory:
        concurrent_scan.scan_devices_parallel(device_ids, include_legacy=False)
        for dev in devices.values():
            db.refresh(dev)

    adopted_rows: list[dict] = []
    for binding in payload.bindings:
        device = devices[binding.device_id]
        row = find_adoptable_binding(
            db,
            device,
            interface_name=binding.interface_name,
            access_mode=binding.access_mode,
            vlan_id=binding.vlan_id,
            inner_vlan_id=binding.inner_vlan_id,
        )
        if not row:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{binding.interface_name} 上未发现可纳管的现网绑定 "
                    f"({binding.access_mode.value}"
                    f"{f' vlan={binding.vlan_id}' if binding.vlan_id else ''})"
                ),
            )
        adopted_rows.append(row)

    circuit = Circuit(
        name=payload.name,
        tenant_id=payload.tenant_id,
        service_type=payload.service_type,
        status=CircuitStatus.ACTIVE,
        adopted=True,
        bandwidth_mbps=payload.bandwidth_mbps or 100,
        description=payload.description or "现网纳管（不下发配置）",
        vlan_id=payload.vlan_id,
        vni=payload.vni,
        vsi_name=payload.vsi_name,
    )
    circuit.code = allocation.next_circuit_code(db)

    primary = adopted_rows[0]
    if circuit.vni is None and primary.get("vni") is not None:
        circuit.vni = int(primary["vni"])
    if not circuit.vsi_name and primary.get("vsi_name"):
        circuit.vsi_name = allocation.normalize_vsi_name(str(primary["vsi_name"]))
    if primary.get("bandwidth_mbps") and payload.bandwidth_mbps is None:
        circuit.bandwidth_mbps = int(primary["bandwidth_mbps"])
    elif primary.get("rate_limit_mbps") and payload.bandwidth_mbps is None:
        circuit.bandwidth_mbps = int(primary["rate_limit_mbps"])

    db.add(circuit)
    db.flush()

    endpoints: list[CircuitEndpoint] = []
    for binding, row in zip(payload.bindings, adopted_rows, strict=True):
        svid = binding.vlan_id or row.get("s_vid")
        endpoint = CircuitEndpoint(
            circuit_id=circuit.id,
            device_id=binding.device_id,
            label=binding.label,
            interface_name=port_inventory._normalize_iface(binding.interface_name),
            access_mode=binding.access_mode,
            vlan_id=svid,
            inner_vlan_id=binding.inner_vlan_id or row.get("c_vid"),
            interface_description=row.get("description"),
        )
        db.add(endpoint)
        endpoints.append(endpoint)
    db.flush()

    asn = None
    for ep in endpoints:
        dev = devices[ep.device_id]
        if dev.bgp_asn:
            asn = dev.bgp_asn
            break
        if dev.site and dev.site.bgp_asn:
            asn = dev.site.bgp_asn
            break

    allocation.auto_allocate_circuit_fields(db, circuit, asn)
    if circuit.vni is not None:
        msg = allocation.vni_unavailable_message(
            db, circuit.vni, exclude_circuit_id=circuit.id, for_adopt=True
        )
        if msg:
            raise HTTPException(status_code=409, detail=msg)
    if circuit.vsi_name:
        msg = allocation.vsi_unavailable_message(
            db, circuit.vsi_name, exclude_circuit_id=circuit.id, for_adopt=True
        )
        if msg:
            raise HTTPException(status_code=409, detail=msg)

    for dev in devices.values():
        port_inventory.scan_device(db, dev, include_legacy=False)

    db.flush()
    bugis_controller.sync_circuit_overlay(db, circuit)
    return circuit
