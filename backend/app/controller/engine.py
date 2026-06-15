"""Bugis SDN controller engine.

This is a self-developed (not market) SDN controller. For a given service it:

  1. Registers the endpoint devices as VTEP peers.
  2. Computes the EVPN control plane for the service's VNI:
       - Type-3 IMET per VTEP (BUM / VTEP membership)
       - Type-2 MAC/IP per attachment (host/gateway reachability)
       - Type-5 IP prefix for L3 services (IRB gateway subnet)
  3. Acts as a route reflector: every VTEP in the VNI learns every route.
  4. Returns a control-plane summary used as the controller's "config job".

Data-plane programming (rendering and pushing device config) is still done via
the vendor drivers by the orchestrator, driven by this controller's decisions.
"""
from __future__ import annotations

import ipaddress
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit, CircuitEndpoint
from app.models.controlplane import EvpnRoute, VtepPeer
from app.models.device import Device
from app.models.enums import EvpnRouteType, ServiceType, VtepStatus


def _synth_mac(vni: int, device_id: int) -> str:
    """Deterministic locally-administered MAC for a (vni, device) pair."""
    return (
        "02:%02x:%02x:%02x:%02x:%02x"
        % (
            (vni >> 16) & 0xFF,
            (vni >> 8) & 0xFF,
            vni & 0xFF,
            (device_id >> 8) & 0xFF,
            device_id & 0xFF,
        )
    )


def _subnet_of(gateway_ip: str, prefixlen: int = 24) -> str:
    try:
        net = ipaddress.ip_network(f"{gateway_ip}/{prefixlen}", strict=False)
        return str(net)
    except ValueError:
        return f"{gateway_ip}/{prefixlen}"


# Controller software version — bumped when control-plane semantics change.
CONTROLLER_VERSION = "1.0.0"

# Honest capability matrix shown in the UI (ready | partial | planned).
CAPABILITIES: list[dict[str, str]] = [
    {
        "key": "vtep_registry",
        "name": "VTEP 注册表",
        "status": "ready",
        "detail": "专线开通时自动注册 VTEP 邻居，维护 VNI 成员关系",
    },
    {
        "key": "evpn_rib",
        "name": "EVPN RIB (Type-2/3/5)",
        "status": "ready",
        "detail": "计算并持久化 IMET、MAC/IP、IP 前缀路由，按 VNI 反射",
    },
    {
        "key": "overlay_topology",
        "name": "Overlay 拓扑计算",
        "status": "ready",
        "detail": "按 VNI 全互联隧道拓扑可视化",
    },
    {
        "key": "data_plane_orchestration",
        "name": "数据面编排",
        "status": "partial",
        "detail": "控制面由本控制器决策，配置渲染/下发仍经南向驱动 (NETCONF/CLI)",
    },
    {
        "key": "state_versioning",
        "name": "状态版本化",
        "status": "ready",
        "detail": "RIB 带时间戳；设备配置在「配置管理」中版本快照与 diff",
    },
    {
        "key": "real_bgp_peering",
        "name": "与设备真实 BGP EVPN 对等",
        "status": "planned",
        "detail": "当前为平台内 RIB 模拟；后续可对接 FRR/设备 BGP 会话",
    },
    {
        "key": "sr_mpls_evpn",
        "name": "SR-MPLS EVPN 控制面",
        "status": "planned",
        "detail": "当前聚焦 VXLAN-EVPN；SR-MPLS 仍走直连南向驱动",
    },
    {
        "key": "controller_ha",
        "name": "控制器集群 / HA",
        "status": "planned",
        "detail": "单实例内嵌控制器，生产需外部化或主备",
    },
]


class BugisController:
    """Self-developed EVPN fabric controller."""

    name = "Bugis SDN Controller"
    version = CONTROLLER_VERSION

    # --- VTEP registry ---------------------------------------------------
    def _register_vtep(self, db: Session, device: Device, vni: int) -> VtepPeer:
        peer = db.execute(
            select(VtepPeer).where(VtepPeer.device_id == device.id)
        ).scalar_one_or_none()
        vtep_ip = device.loopback_ip or device.mgmt_ip
        if peer is None:
            peer = VtepPeer(
                device_id=device.id,
                name=device.name,
                vtep_ip=vtep_ip,
                asn=device.bgp_asn,
                status=VtepStatus.UP,
                vnis="",
            )
            db.add(peer)
            db.flush()
        peer.vtep_ip = vtep_ip
        peer.asn = device.bgp_asn
        peer.status = VtepStatus.UP
        peer.last_seen = datetime.now(timezone.utc)
        vset = {v for v in peer.vnis.split(",") if v}
        vset.add(str(vni))
        peer.vnis = ",".join(sorted(vset, key=int))
        return peer

    def _deregister_vni(self, db: Session, device_id: int, vni: int) -> None:
        peer = db.execute(
            select(VtepPeer).where(VtepPeer.device_id == device_id)
        ).scalar_one_or_none()
        if not peer:
            return
        vset = {v for v in peer.vnis.split(",") if v and v != str(vni)}
        peer.vnis = ",".join(sorted(vset, key=int))

    # --- service install / withdraw -------------------------------------
    def install_circuit(
        self, db: Session, circuit: Circuit, endpoints: list[CircuitEndpoint]
    ) -> dict:
        vni = circuit.vni or 0
        rt = circuit.route_target or f"65000:{vni}"
        is_l3 = circuit.service_type in (ServiceType.L3VPN_EVPN, ServiceType.DCI)

        # Clear any stale routes for this circuit before recomputing.
        db.execute(delete(EvpnRoute).where(EvpnRoute.circuit_id == circuit.id))

        routes: list[EvpnRoute] = []
        vteps: list[VtepPeer] = []
        for ep in endpoints:
            device = ep.device
            if not device:
                continue
            vtep_ip = device.loopback_ip or device.mgmt_ip
            rd = f"{vtep_ip}:{vni}"
            peer = self._register_vtep(db, device, vni)
            vteps.append(peer)

            # Type-3 IMET: advertise this VTEP's membership in the VNI.
            routes.append(EvpnRoute(
                route_type=EvpnRouteType.IMET, vni=vni, rd=rd, rt=rt,
                vtep_ip=vtep_ip, next_hop=vtep_ip,
                circuit_id=circuit.id, origin_device_id=device.id,
            ))
            # Type-2 MAC/IP: synthesized anycast/host entry for the attachment.
            routes.append(EvpnRoute(
                route_type=EvpnRouteType.MAC_IP, vni=vni, rd=rd, rt=rt,
                mac=_synth_mac(vni, device.id),
                ip_addr=ep.gateway_ip or ep.ip_address,
                vtep_ip=vtep_ip, next_hop=vtep_ip,
                circuit_id=circuit.id, origin_device_id=device.id,
            ))
            # Type-5 IP prefix for L3 services (IRB gateway subnet).
            if is_l3 and ep.gateway_ip:
                routes.append(EvpnRoute(
                    route_type=EvpnRouteType.IP_PREFIX, vni=vni, rd=rd, rt=rt,
                    ip_addr=_subnet_of(ep.gateway_ip), vtep_ip=vtep_ip,
                    next_hop=vtep_ip, circuit_id=circuit.id,
                    origin_device_id=device.id,
                ))

        for r in routes:
            db.add(r)
        db.flush()

        return {
            "controller": self.name,
            "vni": vni,
            "rt": rt,
            "vteps": [p.vtep_ip for p in vteps],
            "routes_installed": len(routes),
            "summary": self._render_summary(circuit, vteps, routes),
        }

    def withdraw_circuit(
        self, db: Session, circuit: Circuit, endpoints: list[CircuitEndpoint]
    ) -> dict:
        vni = circuit.vni or 0
        count = db.execute(
            select(EvpnRoute).where(EvpnRoute.circuit_id == circuit.id)
        ).scalars().all()
        db.execute(delete(EvpnRoute).where(EvpnRoute.circuit_id == circuit.id))
        for ep in endpoints:
            if ep.device:
                self._deregister_vni(db, ep.device_id, vni)
        return {
            "controller": self.name,
            "vni": vni,
            "routes_withdrawn": len(count),
            "summary": f"# Bugis SDN Controller withdrew VNI {vni} "
            f"({len(count)} routes) for {circuit.code}",
        }

    def _render_summary(self, circuit: Circuit, vteps, routes) -> str:
        lines = [
            f"# ===== Bugis SDN Controller · EVPN control plane =====",
            f"# service={circuit.code} vni={circuit.vni} "
            f"type={circuit.service_type.value} rt={circuit.route_target}",
            f"# VTEPs ({len(vteps)}): " + ", ".join(p.vtep_ip for p in vteps),
            f"# reflecting {len(routes)} routes to all VTEPs in VNI {circuit.vni}",
            "#",
        ]
        for r in routes:
            if r.route_type == EvpnRouteType.IMET:
                lines.append(f"  [T3 IMET]  rd={r.rd} originator={r.vtep_ip}")
            elif r.route_type == EvpnRouteType.MAC_IP:
                lines.append(
                    f"  [T2 MAC/IP] mac={r.mac} ip={r.ip_addr or '-'} "
                    f"vtep={r.vtep_ip}"
                )
            else:
                lines.append(f"  [T5 PREFIX] {r.ip_addr} via {r.next_hop}")
        return "\n".join(lines)

    # --- queries ---------------------------------------------------------
    def status(self, db: Session) -> dict:
        vteps = db.execute(select(VtepPeer)).scalars().all()
        routes = db.execute(select(EvpnRoute)).scalars().all()
        by_type: dict[str, int] = {}
        vnis: set[int] = set()
        for r in routes:
            by_type[r.route_type.value] = by_type.get(r.route_type.value, 0) + 1
            vnis.add(r.vni)
        return {
            "name": self.name,
            "version": self.version,
            "kind": "builtin",
            "base_url": "internal://bugis",
            "vtep_count": len(vteps),
            "route_count": len(routes),
            "vni_count": len(vnis),
            "routes_by_type": by_type,
            "vteps_up": sum(1 for v in vteps if v.status == VtepStatus.UP),
            "capabilities": CAPABILITIES,
        }


controller = BugisController()
