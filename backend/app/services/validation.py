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
from app.models.device import Device
from app.models.enums import AccessMode, DeviceRole, PathMode, ServiceType
from app.models.site import Site
from app.services import port_inventory


@dataclass
class Issue:
    level: str  # "error" | "warning" | "info"
    code: str
    message: str

    def as_dict(self) -> dict:
        return {"level": self.level, "code": self.code, "message": self.message}


VNI_MIN, VNI_MAX = 1, 16_777_215
VLAN_MIN, VLAN_MAX = 1, 4094
EGRESS_COUNTRIES = frozenset({
    "CN", "HK", "SG", "JP", "US", "GB", "DE", "AU", "TW", "KR",
})


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
    if circuit.service_type in (ServiceType.L3VPN_EVPN, ServiceType.REMOTE_IPT):
        if not circuit.vrf_name:
            issues.append(Issue("error", "missing_vrf", "L3VPN 缺少 VRF 名称"))
        if not any(ep.gateway_ip for ep in circuit.endpoints):
            issues.append(
                Issue("warning", "no_gateway", "L3VPN 未配置任意 IRB 网关地址")
            )

    # Remote IPT: cross-border breakout via dedicated line to foreign public internet
    if circuit.service_type == ServiceType.REMOTE_IPT:
        if len(circuit.endpoints) < 1:
            issues.append(
                Issue("error", "remote_ipt_no_access", "Remote IPT 至少需要一个客户接入端点")
            )
        if not circuit.egress_country:
            issues.append(
                Issue("error", "remote_ipt_country", "Remote IPT 必须指定公网出口国家/地区")
            )
        elif circuit.egress_country.upper() not in EGRESS_COUNTRIES:
            issues.append(
                Issue(
                    "warning", "remote_ipt_country_unknown",
                    f"出口地区 {circuit.egress_country} 不在常用列表，请确认",
                )
            )
        if not circuit.egress_site_id:
            issues.append(
                Issue("error", "remote_ipt_site", "Remote IPT 必须指定出口站点 (PoP)")
            )
        else:
            egress_site = db.get(Site, circuit.egress_site_id)
            if not egress_site:
                issues.append(
                    Issue("error", "remote_ipt_site_missing", "出口站点不存在")
                )
            else:
                borders = db.execute(
                    select(Device).where(
                        Device.site_id == circuit.egress_site_id,
                        Device.role.in_([DeviceRole.DCI_GW, DeviceRole.BORDER_LEAF]),
                    )
                ).scalars().all()
                if not borders:
                    issues.append(
                        Issue(
                            "error", "remote_ipt_no_border",
                            f"出口站点 {egress_site.name} 无边界网关设备",
                        )
                    )
        if not circuit.ipt_public_ip:
            issues.append(
                Issue("warning", "remote_ipt_ip", "未分配公网出口 IP，将自动分配")
            )
        access_sites = {
            ep.device.site_id for ep in circuit.endpoints
            if ep.device and ep.device.site_id
        }
        if circuit.egress_site_id and access_sites == {circuit.egress_site_id}:
            issues.append(
                Issue(
                    "warning", "remote_ipt_same_site",
                    "接入与出口在同一站点，Remote IPT 通常用于跨境公网出口",
                )
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

    # S-VID / port encapsulation collision (platform + device inventory)
    for ep in circuit.endpoints:
        if not ep.device_id or not ep.interface_name:
            continue
        svid = ep.vlan_id or circuit.vlan_id
        mode = ep.access_mode or AccessMode.DOT1Q
        ok, msg = port_inventory.check_endpoint_available(
            db,
            ep.device_id,
            ep.interface_name,
            svid,
            ep.inner_vlan_id,
            mode,
            exclude_circuit_id=circuit.id,
        )
        if not ok and msg:
            issues.append(
                Issue(
                    "error",
                    "svid_collision",
                    f"端点 {ep.label} ({ep.interface_name}): {msg}",
                )
            )

    # Explicit SR path validation
    if circuit.path_mode == PathMode.EXPLICIT_SR:
        from app.services import path_service

        chain = path_service.full_path_for_circuit(db, circuit)
        ok, msg = path_service.supports_explicit_sr(chain)
        if not ok:
            issues.append(Issue("error", "path_unsupported", msg or "路径不支持"))
        for err in path_service.validate_connectivity(db, [d.id for d in chain]):
            issues.append(Issue("error", "path_connectivity", err))
    elif circuit.path_hops:
        issues.append(
            Issue(
                "warning", "path_ignored",
                "VXLAN/OSPF 专线忽略了经由设备，实际按 IGP 最短路径转发",
            )
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
