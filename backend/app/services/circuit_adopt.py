"""Adopt existing on-box S-VID bindings into platform inventory without config push."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.circuit import Circuit, CircuitEndpoint
from app.models.device import Device
from app.models.enums import AccessMode, CircuitStatus, ServiceType
from app.models.tenant import Tenant
from app.schemas.circuit import CircuitAdoptBinding, CircuitAdoptCreate, CircuitEndpointCreate
from app.services import allocation, port_inventory


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

        port_inventory.scan_device(db, device, include_legacy=False)
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
    key = _binding_key(interface_name, mode, vlan_id, inner_vlan_id)
    for row in bindings.get("items") or []:
        row_key = _binding_key(
            row["interface_name"],
            row.get("access_mode") or "dot1q",
            row.get("s_vid"),
            row.get("c_vid"),
        )
        if row_key != key:
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

    device_ids = {b.device_id for b in payload.bindings}
    devices: dict[int, Device] = {}
    for did in device_ids:
        dev = db.get(Device, did)
        if not dev:
            raise HTTPException(status_code=404, detail=f"device {did} not found")
        port_inventory.scan_device(db, dev, include_legacy=False)
        devices[did] = dev

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
        msg = allocation.vni_unavailable_message(db, circuit.vni, exclude_circuit_id=circuit.id)
        if msg:
            raise HTTPException(status_code=409, detail=msg)
    if circuit.vsi_name:
        msg = allocation.vsi_unavailable_message(
            db, circuit.vsi_name, exclude_circuit_id=circuit.id
        )
        if msg:
            raise HTTPException(status_code=409, detail=msg)

    for dev in devices.values():
        port_inventory.scan_device(db, dev, include_legacy=False)

    db.flush()
    return circuit
