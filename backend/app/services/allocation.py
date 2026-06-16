"""Resource allocation: VNI, VLAN, RD/RT, circuit codes.

Keeps allocation deterministic and collision-free by inspecting existing
circuits. In a production system these pools would be backed by a dedicated
IPAM/identifier service.
"""
from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.circuit import Circuit

VNI_BASE = 10000
VNI_MAX = 16_777_215
VLAN_BASE = 100
VLAN_MAX = 4000
VSI_MAX_LEN = 63


def _used_vnis(db: Session) -> set[int]:
    rows = db.execute(select(Circuit.vni).where(Circuit.vni.is_not(None))).all()
    used = {r[0] for r in rows}
    if settings.smart_overlay_allocation:
        from app.services.overlay_inventory import network_reserved_vnis

        used |= network_reserved_vnis(db)
    return used


def _used_vsis(db: Session) -> set[str]:
    rows = db.execute(
        select(Circuit.vsi_name).where(Circuit.vsi_name.is_not(None))
    ).all()
    used = {r[0] for r in rows}
    if settings.smart_overlay_allocation:
        from app.services.overlay_inventory import network_reserved_vsis

        used |= network_reserved_vsis(db)
    return used


def build_vsi_name(code: str) -> str:
    """Default VSI name derived from circuit code (H3C-safe)."""
    return f"vsi_{code.replace('-', '_').lower()}"[:VSI_MAX_LEN]


def normalize_vsi_name(name: str) -> str:
    return name.strip()[:VSI_MAX_LEN]


def allocate_vsi(db: Session, code: str) -> str:
    used = _used_vsis(db)
    base = build_vsi_name(code)
    if base not in used:
        return base
    candidate = base
    n = 2
    while candidate in used:
        suffix = f"_{n}"
        candidate = f"{base[: VSI_MAX_LEN - len(suffix)]}{suffix}"
        n += 1
    return candidate


def vni_in_use(db: Session, vni: int, *, exclude_circuit_id: int | None = None) -> Circuit | None:
    stmt = select(Circuit).where(Circuit.vni == vni)
    if exclude_circuit_id is not None:
        stmt = stmt.where(Circuit.id != exclude_circuit_id)
    return db.execute(stmt).scalars().first()


def vsi_in_use(db: Session, vsi_name: str, *, exclude_circuit_id: int | None = None) -> Circuit | None:
    stmt = select(Circuit).where(Circuit.vsi_name == vsi_name)
    if exclude_circuit_id is not None:
        stmt = stmt.where(Circuit.id != exclude_circuit_id)
    return db.execute(stmt).scalars().first()


def vni_unavailable_message(
    db: Session, vni: int, *, exclude_circuit_id: int | None = None
) -> str | None:
    other = vni_in_use(db, vni, exclude_circuit_id=exclude_circuit_id)
    if other:
        return f"VNI {vni} 已被专线 {other.code} 占用"
    if settings.smart_overlay_allocation:
        from app.services.overlay_inventory import vni_conflict_on_network

        conflict = vni_conflict_on_network(db, vni, exclude_circuit_id=exclude_circuit_id)
        if conflict:
            return conflict["message"]
    return None


def vsi_unavailable_message(
    db: Session, vsi_name: str, *, exclude_circuit_id: int | None = None
) -> str | None:
    other = vsi_in_use(db, vsi_name, exclude_circuit_id=exclude_circuit_id)
    if other:
        return f"VSI {vsi_name} 已被专线 {other.code} 占用"
    if settings.smart_overlay_allocation:
        from app.services.overlay_inventory import vsi_conflict_on_network

        conflict = vsi_conflict_on_network(
            db, vsi_name, exclude_circuit_id=exclude_circuit_id
        )
        if conflict:
            return conflict["message"]
    return None


def _used_vlans(db: Session) -> set[int]:
    rows = db.execute(
        select(Circuit.vlan_id).where(Circuit.vlan_id.is_not(None))
    ).all()
    return {r[0] for r in rows}


def allocate_vni(db: Session) -> int:
    used = _used_vnis(db)
    candidate = VNI_BASE
    while candidate in used and candidate < VNI_MAX:
        candidate += 1
    return candidate


def allocate_vlan(db: Session) -> int:
    used = _used_vlans(db)
    candidate = VLAN_BASE
    while candidate in used and candidate < VLAN_MAX:
        candidate += 1
    return candidate


def next_circuit_code(db: Session) -> str:
    """Generate a unique circuit code like CIR-AB12CD."""
    while True:
        code = "CIR-" + secrets.token_hex(3).upper()
        exists = db.execute(
            select(Circuit.id).where(Circuit.code == code)
        ).first()
        if not exists:
            return code


def build_rd(asn: int | None, vni: int) -> str:
    """Route distinguisher in ASN:NN format."""
    return f"{asn or 65000}:{vni}"


def build_rt(asn: int | None, vni: int) -> str:
    """Route target in ASN:NN format."""
    return f"{asn or 65000}:{vni}"


def build_vrf_name(code: str) -> str:
    return f"vrf_{code.replace('-', '_').lower()}"


def allocate_public_ip(db: Session, vni: int) -> str:
    """Deterministic demo public IP for Remote IPT breakout."""
    used = {
        r[0]
        for r in db.execute(
            select(Circuit.ipt_public_ip).where(Circuit.ipt_public_ip.is_not(None))
        ).all()
        if r[0]
    }
    # 203.x.y.z pool for lab/demo
    base = 203
    second = 100 + (vni % 100)
    third = (vni // 100) % 200
    for host in range(1, 254):
        candidate = f"{base}.{second}.{third}.{host}"
        if candidate not in used:
            return candidate
    return f"{base}.{second}.{third}.254"


def auto_allocate_circuit_fields(db: Session, circuit: Circuit, asn: int | None) -> None:
    """Fill in any unset EVPN identifiers on a circuit in-place."""
    if circuit.vni is None:
        circuit.vni = allocate_vni(db)
    if not circuit.vsi_name:
        circuit.vsi_name = allocate_vsi(db, circuit.code)
    if circuit.vlan_id is None:
        circuit.vlan_id = allocate_vlan(db)
    if not circuit.route_distinguisher:
        circuit.route_distinguisher = build_rd(asn, circuit.vni)
    if not circuit.route_target:
        circuit.route_target = build_rt(asn, circuit.vni)
    if not circuit.vrf_name:
        circuit.vrf_name = build_vrf_name(circuit.code)
    from app.models.enums import ServiceType

    if circuit.service_type == ServiceType.REMOTE_IPT and not circuit.ipt_public_ip:
        circuit.ipt_public_ip = allocate_public_ip(db, circuit.vni)
