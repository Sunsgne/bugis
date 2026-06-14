"""Resource allocation: VNI, VLAN, RD/RT, circuit codes.

Keeps allocation deterministic and collision-free by inspecting existing
circuits. In a production system these pools would be backed by a dedicated
IPAM/identifier service.
"""
from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit

VNI_BASE = 10000
VNI_MAX = 16_000_000
VLAN_BASE = 100
VLAN_MAX = 4000


def _used_vnis(db: Session) -> set[int]:
    rows = db.execute(select(Circuit.vni).where(Circuit.vni.is_not(None))).all()
    return {r[0] for r in rows}


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


def auto_allocate_circuit_fields(db: Session, circuit: Circuit, asn: int | None) -> None:
    """Fill in any unset EVPN identifiers on a circuit in-place."""
    if circuit.vni is None:
        circuit.vni = allocate_vni(db)
    if circuit.vlan_id is None:
        circuit.vlan_id = allocate_vlan(db)
    if not circuit.route_distinguisher:
        circuit.route_distinguisher = build_rd(asn, circuit.vni)
    if not circuit.route_target:
        circuit.route_target = build_rt(asn, circuit.vni)
    if not circuit.vrf_name:
        circuit.vrf_name = build_vrf_name(circuit.code)
