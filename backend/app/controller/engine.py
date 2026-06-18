"""Bugis SDN controller engine."""
from __future__ import annotations

import ipaddress
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.controller import bgp_peering, dataplane, ha, srmpls
from app.models.circuit import Circuit, CircuitEndpoint
from app.models.controlplane import BgpEvpnSession, EvpnRoute, VtepPeer
from app.models.device import Device
from app.models.enums import BgpSessionState, CircuitStatus, EvpnEncap, EvpnRouteType, ServiceType, VtepStatus


def _synth_mac(vni: int, device_id: int) -> str:
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


CONTROLLER_VERSION = "2.0.0"

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
        "detail": "按 VNI 全互联隧道拓扑可视化（VXLAN / SR-MPLS）",
    },
    {
        "key": "data_plane_orchestration",
        "name": "数据面编排",
        "status": "ready",
        "detail": "控制面决策后由控制器统一调度南向驱动渲染/下发，并跟踪每端状态",
    },
    {
        "key": "state_versioning",
        "name": "状态版本化",
        "status": "ready",
        "detail": "RIB 带版本号与集群同步；设备配置在「配置管理」中版本快照与 diff",
    },
    {
        "key": "real_bgp_peering",
        "name": "与设备真实 BGP EVPN 对等",
        "status": "ready",
        "detail": "自动建立 BGP EVPN 会话（FRR/设备），RIB 双向同步与 keepalive 探测",
    },
    {
        "key": "sr_mpls_evpn",
        "name": "SR-MPLS EVPN 控制面",
        "status": "ready",
        "detail": "SR-MPLS 设备路由携带 MPLS 标签与 SR SID，与 VXLAN 控制面统一 RIB",
    },
    {
        "key": "controller_ha",
        "name": "控制器集群 / HA",
        "status": "ready",
        "detail": "主备节点注册、RIB 版本同步、心跳检测（active-standby）",
    },
]


class BugisController:
    """Self-developed EVPN fabric controller."""

    name = "Bugis SDN Controller"
    version = CONTROLLER_VERSION

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

    def sync_circuit_overlay(
        self,
        db: Session,
        circuit: Circuit,
        *,
        work_order_id: int | None = None,
    ) -> dict | None:
        """Register or refresh VTEP/EVPN state for inventory-managed circuits.

        Used when a circuit is adopted from the network or endpoints change
        without a southbound config push — the overlay graph should still update.
        """
        if circuit.vni is None or not circuit.endpoints:
            return None
        if circuit.status not in (
            CircuitStatus.PENDING,
            CircuitStatus.PROVISIONING,
            CircuitStatus.ACTIVE,
            CircuitStatus.DEGRADED,
            CircuitStatus.SUSPENDED,
        ):
            return None

        endpoints: list[CircuitEndpoint] = []
        for ep in circuit.endpoints:
            if not ep.device_id:
                continue
            if ep.device is None:
                ep.device = db.get(Device, ep.device_id)
            if ep.device:
                endpoints.append(ep)
        if not endpoints:
            return None
        return self.install_circuit(db, circuit, endpoints, work_order_id=work_order_id)

    def install_circuit(
        self,
        db: Session,
        circuit: Circuit,
        endpoints: list[CircuitEndpoint],
        work_order_id: int | None = None,
    ) -> dict:
        vni = circuit.vni or 0
        rt = circuit.route_target or f"65000:{vni}"
        is_l3 = circuit.service_type in (
            ServiceType.L3VPN_EVPN, ServiceType.DCI, ServiceType.REMOTE_IPT,
        )

        db.execute(delete(EvpnRoute).where(EvpnRoute.circuit_id == circuit.id))

        routes: list[EvpnRoute] = []
        vteps: list[VtepPeer] = []
        devices: list[Device] = []
        for ep in endpoints:
            device = ep.device
            if not device:
                continue
            devices.append(device)
            vtep_ip = device.loopback_ip or device.mgmt_ip
            rd = f"{vtep_ip}:{vni}"
            peer = self._register_vtep(db, device, vni)
            vteps.append(peer)

            encap = (
                EvpnEncap.MPLS
                if device.overlay_tech.value == "sr_mpls_evpn"
                else EvpnEncap.VXLAN
            )
            routes.append(EvpnRoute(
                route_type=EvpnRouteType.IMET, vni=vni, rd=rd, rt=rt,
                vtep_ip=vtep_ip, next_hop=vtep_ip,
                circuit_id=circuit.id, origin_device_id=device.id, encap=encap,
            ))
            routes.append(EvpnRoute(
                route_type=EvpnRouteType.MAC_IP, vni=vni, rd=rd, rt=rt,
                mac=_synth_mac(vni, device.id),
                ip_addr=ep.gateway_ip or ep.ip_address,
                vtep_ip=vtep_ip, next_hop=vtep_ip,
                circuit_id=circuit.id, origin_device_id=device.id, encap=encap,
            ))
            if is_l3 and ep.gateway_ip:
                routes.append(EvpnRoute(
                    route_type=EvpnRouteType.IP_PREFIX, vni=vni, rd=rd, rt=rt,
                    ip_addr=_subnet_of(ep.gateway_ip), vtep_ip=vtep_ip,
                    next_hop=vtep_ip, circuit_id=circuit.id,
                    origin_device_id=device.id, encap=encap,
                ))

        for r in routes:
            db.add(r)
        db.flush()

        mpls_count = srmpls.enrich_routes(db, routes, endpoints, circuit)
        from app.services import path_service

        path_segments = path_service.segment_list(
            path_service.full_path_for_circuit(db, circuit)
        )
        bgp_sessions = bgp_peering.ensure_sessions(db, devices)
        bgp_peering.sync_sessions(db)
        rib_version = ha.bump_rib_version(db)
        dp_bindings = dataplane.plan_bindings(
            db, circuit, endpoints, "apply", work_order_id
        )

        return {
            "controller": self.name,
            "vni": vni,
            "rt": rt,
            "vteps": [p.vtep_ip for p in vteps],
            "routes_installed": len(routes),
            "mpls_routes": mpls_count,
            "bgp_sessions": len(bgp_sessions),
            "rib_version": rib_version,
            "dataplane_bindings": len(dp_bindings),
            "path_mode": circuit.path_mode.value,
            "path_segments": path_segments,
            "summary": self._render_summary(
                circuit, vteps, routes, bgp_sessions, path_segments
            ),
        }

    def withdraw_circuit(
        self, db: Session, circuit: Circuit, endpoints: list[CircuitEndpoint],
        work_order_id: int | None = None,
    ) -> dict:
        vni = circuit.vni or 0
        count = db.execute(
            select(EvpnRoute).where(EvpnRoute.circuit_id == circuit.id)
        ).scalars().all()
        db.execute(delete(EvpnRoute).where(EvpnRoute.circuit_id == circuit.id))
        for ep in endpoints:
            if ep.device:
                self._deregister_vni(db, ep.device_id, vni)
        dataplane.plan_bindings(db, circuit, endpoints, "remove", work_order_id)
        ha.bump_rib_version(db)
        bgp_peering.sync_sessions(db)
        return {
            "controller": self.name,
            "vni": vni,
            "routes_withdrawn": len(count),
            "summary": f"# Bugis SDN Controller withdrew VNI {vni} "
            f"({len(count)} routes) for {circuit.code}",
        }

    def purge_circuit(self, db: Session, circuit: Circuit) -> dict:
        """Remove all controller overlay state for a circuit being deleted.

        Deletes the circuit's EVPN routes and deregisters its VNI from each
        endpoint device's VTEP so the overlay topology graph does not keep a
        stale edge after a (failed) circuit is removed.
        """
        vni = circuit.vni or 0
        routes = db.execute(
            select(EvpnRoute).where(EvpnRoute.circuit_id == circuit.id)
        ).scalars().all()
        db.execute(delete(EvpnRoute).where(EvpnRoute.circuit_id == circuit.id))
        for ep in circuit.endpoints:
            if ep.device_id:
                self._deregister_vni(db, ep.device_id, vni)
        if routes or vni:
            ha.bump_rib_version(db)
        return {"vni": vni, "routes_removed": len(routes)}

    def _render_summary(
        self,
        circuit: Circuit,
        vteps,
        routes,
        bgp_sessions: list[BgpEvpnSession],
        path_segments: list[int] | None = None,
    ) -> str:
        lines = [
            "# ===== Bugis SDN Controller · EVPN control plane =====",
            f"# service={circuit.code} vni={circuit.vni} "
            f"type={circuit.service_type.value} rt={circuit.route_target}",
            f"# path_mode={circuit.path_mode.value}"
            + (
                f" sr_segments={' -> '.join(str(s) for s in path_segments)}"
                if path_segments
                else ""
            ),
            f"# VTEPs ({len(vteps)}): " + ", ".join(p.vtep_ip for p in vteps),
            f"# reflecting {len(routes)} routes · BGP peers {len(bgp_sessions)}",
            "#",
        ]
        for r in routes:
            enc = f" encap={r.encap.value}" if r.encap else ""
            lbl = f" label={r.mpls_label}" if r.mpls_label else ""
            if r.route_type == EvpnRouteType.IMET:
                lines.append(f"  [T3 IMET]  rd={r.rd} originator={r.vtep_ip}{enc}{lbl}")
            elif r.route_type == EvpnRouteType.MAC_IP:
                lines.append(
                    f"  [T2 MAC/IP] mac={r.mac} ip={r.ip_addr or '-'} "
                    f"vtep={r.vtep_ip}{enc}{lbl}"
                )
            else:
                lines.append(f"  [T5 PREFIX] {r.ip_addr} via {r.next_hop}{enc}{lbl}")
        if bgp_sessions:
            lines.append("# BGP EVPN sessions:")
            for s in bgp_sessions:
                lines.append(
                    f"  peer {s.peer_ip} as {s.remote_asn} state={s.state.value}"
                )
        return "\n".join(lines)

    def status(self, db: Session) -> dict:
        vteps = db.execute(select(VtepPeer)).scalars().all()
        routes = db.execute(select(EvpnRoute)).scalars().all()
        by_type: dict[str, int] = {}
        by_encap: dict[str, int] = {}
        vnis: set[int] = set()
        for r in routes:
            by_type[r.route_type.value] = by_type.get(r.route_type.value, 0) + 1
            by_encap[r.encap.value] = by_encap.get(r.encap.value, 0) + 1
            vnis.add(r.vni)
        bgp_up = db.scalar(
            select(func.count(BgpEvpnSession.id)).where(
                BgpEvpnSession.state == BgpSessionState.ESTABLISHED
            )
        ) or 0
        cluster = ha.cluster_status(db)
        return {
            "name": self.name,
            "version": self.version,
            "kind": "builtin",
            "base_url": "internal://bugis",
            "vtep_count": len(vteps),
            "route_count": len(routes),
            "vni_count": len(vnis),
            "routes_by_type": by_type,
            "routes_by_encap": by_encap,
            "vteps_up": sum(1 for v in vteps if v.status == VtepStatus.UP),
            "bgp_sessions_up": int(bgp_up),
            "rib_version": cluster.get("rib_version", 0),
            "cluster": cluster,
            "capabilities": CAPABILITIES,
            "capabilities_ready": sum(
                1 for c in CAPABILITIES if c["status"] == "ready"
            ),
            "capabilities_total": len(CAPABILITIES),
        }


controller = BugisController()
