"""Rich template context for circuit / backbone link alarm notifications."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit, CircuitEndpoint
from app.models.device import Device
from app.models.enums import AccessMode
from app.models.link import Link


def _svid_label(ep: CircuitEndpoint) -> str:
    mode = ep.access_mode.value if ep.access_mode else AccessMode.DOT1Q.value
    if mode == AccessMode.QINQ.value and ep.inner_vlan_id:
        outer = ep.vlan_id if ep.vlan_id is not None else "—"
        return f"S-VID {outer} C-VID {ep.inner_vlan_id}"
    if ep.vlan_id is not None:
        return f"S-VID {ep.vlan_id}"
    return "—"


def _endpoint_row(ep: CircuitEndpoint | None, db: Session) -> dict[str, str]:
    if not ep:
        return {"device": "—", "port": "—", "svid": "—"}
    device = ep.device
    if device is None and ep.device_id:
        device = db.get(Device, ep.device_id)
    return {
        "device": device.name if device else f"#{ep.device_id}",
        "port": ep.interface_name or "—",
        "svid": _svid_label(ep),
    }


def circuit_alarm_context(db: Session, circuit: Circuit) -> dict[str, str | int | float]:
    """Variables for circuit-kind alarm templates."""
    tenant = circuit.tenant
    if tenant is None and circuit.tenant_id:
        from app.models.tenant import Tenant

        tenant = db.get(Tenant, circuit.tenant_id)

    eps = sorted(circuit.endpoints or [], key=lambda e: (e.label != "A", e.label))
    ep_a = next((e for e in eps if e.label == "A"), eps[0] if eps else None)
    ep_z = next((e for e in eps if e.label == "Z"), eps[1] if len(eps) > 1 else None)

    a = _endpoint_row(ep_a, db)
    z = _endpoint_row(ep_z, db)

    tenant_name = tenant.name if tenant else "—"
    circuit_name = circuit.name or circuit.code
    service = circuit.service_type.value if circuit.service_type else "—"

    endpoint_summary = (
        f"A端 {a['device']} {a['port']} {a['svid']} · "
        f"Z端 {z['device']} {z['port']} {z['svid']}"
    )

    return {
        "circuit_code": circuit.code,
        "circuit_name": circuit_name,
        "tenant_name": tenant_name,
        "service_type": service,
        "bandwidth_mbps": circuit.bandwidth_mbps,
        "endpoint_summary": endpoint_summary,
        "endpoint_a_device": a["device"],
        "endpoint_a_port": a["port"],
        "endpoint_a_svid": a["svid"],
        "endpoint_z_device": z["device"],
        "endpoint_z_port": z["port"],
        "endpoint_z_svid": z["svid"],
    }


def link_alarm_context(db: Session, link: Link) -> dict[str, str | int]:
    """Variables for backbone link alarm templates."""
    dev_a = db.get(Device, link.device_a_id)
    dev_z = db.get(Device, link.device_z_id)
    device_a = dev_a.name if dev_a else f"#{link.device_a_id}"
    device_z = dev_z.name if dev_z else f"#{link.device_z_id}"
    interface_a = link.interface_a or "—"
    interface_z = link.interface_z or "—"
    supplier = (link.supplier or "").strip() or "—"

    endpoint_summary = (
        f"A端 {device_a} {interface_a} · Z端 {device_z} {interface_z}"
    )

    return {
        "link_name": link.name,
        "supplier": supplier,
        "device_a_name": device_a,
        "device_z_name": device_z,
        "interface_a": interface_a,
        "interface_z": interface_z,
        "link_capacity_mbps": link.capacity_mbps,
        "endpoint_summary": endpoint_summary,
    }
