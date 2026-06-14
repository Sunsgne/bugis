"""Pre-flight configuration / intent validation.

Runs compliance checks on a circuit before provisioning so operators catch
mistakes (missing identifiers, range violations, RD/RT collisions, naming and
MTU issues) before any configuration reaches devices.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit
from app.models.enums import ServiceType


@dataclass
class Issue:
    level: str  # "error" | "warning" | "info"
    code: str
    message: str

    def as_dict(self) -> dict:
        return {"level": self.level, "code": self.code, "message": self.message}


VNI_MIN, VNI_MAX = 1, 16_777_215
VLAN_MIN, VLAN_MAX = 1, 4094


def validate_circuit(db: Session, circuit: Circuit) -> list[Issue]:
    issues: list[Issue] = []

    # Endpoints present
    if not circuit.endpoints:
        issues.append(Issue("error", "no_endpoints", "专线没有任何接入端点"))

    # EVPN identifiers
    if circuit.vni is None:
        issues.append(Issue("error", "missing_vni", "缺少 VNI"))
    elif not (VNI_MIN <= circuit.vni <= VNI_MAX):
        issues.append(Issue("error", "vni_range", f"VNI {circuit.vni} 超出范围"))

    if circuit.vlan_id is not None and not (VLAN_MIN <= circuit.vlan_id <= VLAN_MAX):
        issues.append(Issue("error", "vlan_range", f"VLAN {circuit.vlan_id} 超出范围"))

    if not circuit.route_distinguisher:
        issues.append(Issue("error", "missing_rd", "缺少 Route Distinguisher"))
    if not circuit.route_target:
        issues.append(Issue("error", "missing_rt", "缺少 Route Target"))

    # L3 services need a gateway IP on at least one endpoint
    if circuit.service_type == ServiceType.L3VPN_EVPN:
        if not circuit.vrf_name:
            issues.append(Issue("error", "missing_vrf", "L3VPN 缺少 VRF 名称"))
        if not any(ep.gateway_ip for ep in circuit.endpoints):
            issues.append(
                Issue("warning", "no_gateway", "L3VPN 未配置任意 IRB 网关地址")
            )

    # Bandwidth & MTU sanity
    if circuit.bandwidth_mbps <= 0:
        issues.append(Issue("error", "bandwidth", "带宽必须大于 0"))
    if circuit.mtu < 1500:
        issues.append(Issue("warning", "mtu_low", f"MTU {circuit.mtu} 偏低 (<1500)"))

    # RD/RT collision with a different circuit
    if circuit.route_distinguisher:
        other = db.execute(
            select(Circuit).where(
                Circuit.route_distinguisher == circuit.route_distinguisher,
                Circuit.id != circuit.id,
            )
        ).scalars().first()
        if other:
            issues.append(
                Issue(
                    "error", "rd_collision",
                    f"RD {circuit.route_distinguisher} 与专线 {other.code} 冲突",
                )
            )

    # VNI collision
    if circuit.vni is not None:
        other = db.execute(
            select(Circuit).where(
                Circuit.vni == circuit.vni, Circuit.id != circuit.id
            )
        ).scalars().first()
        if other:
            issues.append(
                Issue("error", "vni_collision",
                      f"VNI {circuit.vni} 与专线 {other.code} 冲突")
            )

    # Endpoint interface naming present
    for ep in circuit.endpoints:
        if not ep.interface_name or ep.interface_name in ("-", ""):
            issues.append(
                Issue("warning", "iface_name",
                      f"端点 {ep.label} 接口名缺失")
            )

    return issues


def summarize(issues: list[Issue]) -> dict:
    errors = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warning"]
    return {
        "ok": len(errors) == 0,
        "errors": len(errors),
        "warnings": len(warnings),
        "issues": [i.as_dict() for i in issues],
    }
