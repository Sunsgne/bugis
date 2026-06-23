"""Three-layer circuit forwarding path: business (EVPN) + control + underlay."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit, CircuitEndpoint
from app.models.controlplane import BgpEvpnSession, EvpnRoute, VtepPeer
from app.models.device import Device
from app.models.enums import PathMode
from app.services import igp_cost_service, path_service, probe_log_service
from app.services.circuit_probe.path import resolve_underlay_path


def _ordered_endpoints(circuit: Circuit) -> list[CircuitEndpoint]:
    return sorted(circuit.endpoints, key=lambda e: (e.label != "A", e.label, e.id))


def _access_mode_label(mode: str | None) -> str:
    labels = {
        "dot1q": "802.1Q",
        "qinq": "QinQ",
        "access": "Access/Untagged",
    }
    return labels.get(mode or "dot1q", mode or "dot1q")


def _find_access_binding_for_endpoint(
    db: Session,
    device: Device,
    ep: CircuitEndpoint,
    circuit: Circuit,
) -> dict | None:
    inv = igp_cost_service._latest_inventory_dict(db, device.id)
    if not inv:
        return None
    iface = ep.interface_name
    for raw in inv.get("access_bindings") or []:
        if iface and str(raw.get("interface") or "") == iface:
            return raw
    vsi = circuit.vsi_name
    vni = circuit.vni
    for raw in inv.get("access_bindings") or []:
        if vsi and raw.get("vsi_name") == vsi:
            return raw
        if vni is not None and raw.get("vni") == vni:
            return raw
    for raw in inv.get("l2_services") or []:
        if vsi and raw.get("name") == vsi:
            return raw
        if vni is not None and raw.get("vni") == vni:
            return raw
    return None


def _build_business_plane(db: Session, circuit: Circuit) -> dict:
    eps = _ordered_endpoints(circuit)
    multipoint = len(eps) > 2
    hops: list[dict] = []
    endpoint_summaries: list[dict] = []
    seq = 0

    for ep in eps:
        device = ep.device or db.get(Device, ep.device_id)
        if not device:
            continue
        binding = _find_access_binding_for_endpoint(db, device, ep, circuit)
        vlan_label = (
            f"S-VID {ep.vlan_id}" if ep.vlan_id is not None
            else ("无 VLAN (Access)" if ep.access_mode == "access" else "VLAN 自动")
        )
        if ep.access_mode == "qinq" and ep.inner_vlan_id is not None:
            vlan_label = f"S:{ep.vlan_id} C:{ep.inner_vlan_id}"

        endpoint_summaries.append({
            "label": ep.label,
            "device_id": device.id,
            "device_name": device.name,
            "interface": ep.interface_name,
            "access_mode": _access_mode_label(ep.access_mode),
            "vlan": vlan_label,
            "vtep_ip": device.loopback_ip,
            "overlay_tech": device.overlay_tech.value,
        })

        hops.append({
            "sequence": seq,
            "layer": "access",
            "endpoint_label": ep.label,
            "device_id": device.id,
            "device_name": device.name,
            "interface": ep.interface_name,
            "access_mode": _access_mode_label(ep.access_mode),
            "vlan": vlan_label,
            "vsi_name": binding.get("vsi_name") if binding else circuit.vsi_name,
            "vni": binding.get("vni") if binding else circuit.vni,
            "source": "platform" if not binding else "learned",
            "detail": f"{ep.label} 端接入 {device.name} {ep.interface_name or '—'}",
        })
        seq += 1

        hops.append({
            "sequence": seq,
            "layer": "evpn_encap",
            "endpoint_label": ep.label,
            "device_id": device.id,
            "device_name": device.name,
            "vtep_ip": device.loopback_ip,
            "vni": circuit.vni,
            "vsi_name": circuit.vsi_name,
            "rd": circuit.route_distinguisher,
            "rt": circuit.route_target,
            "overlay_tech": device.overlay_tech.value,
            "detail": (
                f"{ep.label} · VTEP {device.loopback_ip or '—'} · "
                f"VNI {circuit.vni or '—'} · {device.overlay_tech.value}"
            ),
        })
        seq += 1

    if multipoint:
        hops.append({
            "sequence": seq,
            "layer": "evpn_instance",
            "vni": circuit.vni,
            "vsi_name": circuit.vsi_name,
            "rd": circuit.route_distinguisher,
            "rt": circuit.route_target,
            "endpoint_count": len(endpoint_summaries),
            "detail": (
                f"多点 EVPN 实例 · VNI {circuit.vni or '—'} · "
                f"{len(endpoint_summaries)} 个 PE 接入 · 二层互通"
            ),
        })
    elif len(eps) >= 2:
        a_dev = eps[0].device or db.get(Device, eps[0].device_id)
        z_dev = eps[-1].device or db.get(Device, eps[-1].device_id)
        if a_dev and z_dev:
            hops.append({
                "sequence": seq,
                "layer": "evpn_tunnel",
                "source_device_id": a_dev.id,
                "source_device": a_dev.name,
                "source_vtep": a_dev.loopback_ip,
                "target_device_id": z_dev.id,
                "target_device": z_dev.name,
                "target_vtep": z_dev.loopback_ip,
                "vni": circuit.vni,
                "vsi_name": circuit.vsi_name,
                "detail": (
                    f"EVPN 隧道 {a_dev.name} ({a_dev.loopback_ip or '—'}) → "
                    f"{z_dev.name} ({z_dev.loopback_ip or '—'}) · VNI {circuit.vni or '—'}"
                ),
            })

    return {
        "topology": "multipoint" if multipoint else "point_to_point",
        "endpoint_count": len(endpoint_summaries),
        "endpoints": endpoint_summaries,
        "service_type": circuit.service_type.value if circuit.service_type else None,
        "vni": circuit.vni,
        "vsi_name": circuit.vsi_name,
        "rd": circuit.route_distinguisher,
        "rt": circuit.route_target,
        "hops": hops,
    }


def _build_control_plane(db: Session, circuit: Circuit) -> dict:
    eps = _ordered_endpoints(circuit)
    vteps: list[dict] = []
    for ep in eps:
        device = ep.device or db.get(Device, ep.device_id)
        if not device:
            continue
        peer = db.execute(
            select(VtepPeer).where(VtepPeer.device_id == device.id)
        ).scalar_one_or_none()
        vni_list: list[int] = []
        if peer and peer.vnis:
            for part in peer.vnis.split(","):
                part = part.strip()
                if part.isdigit():
                    vni_list.append(int(part))
        vteps.append({
            "device_id": device.id,
            "device_name": device.name,
            "endpoint_label": ep.label,
            "vtep_ip": peer.vtep_ip if peer else device.loopback_ip,
            "status": peer.status.value if peer else "unknown",
            "vnis": vni_list,
            "serves_circuit_vni": circuit.vni in vni_list if circuit.vni else False,
            "source": "controller" if peer else "inferred",
        })

    route_filters = [EvpnRoute.circuit_id == circuit.id]
    if circuit.vni is not None:
        route_filters.append(EvpnRoute.vni == circuit.vni)
    route_stmt = select(EvpnRoute).where(or_(*route_filters)).order_by(
        EvpnRoute.route_type, EvpnRoute.id
    )
    routes = db.execute(route_stmt).scalars().all()
    route_rows = [
        {
            "route_type": r.route_type.value,
            "vni": r.vni,
            "rd": r.rd,
            "rt": r.rt,
            "mac": r.mac,
            "ip_addr": r.ip_addr,
            "vtep_ip": r.vtep_ip,
            "next_hop": r.next_hop,
            "origin_device_id": r.origin_device_id,
            "encap": r.encap.value,
            "sr_sid": r.sr_sid,
            "mpls_label": r.mpls_label,
        }
        for r in routes
    ]

    bgp_sessions: list[dict] = []
    for ep in eps:
        device = ep.device or db.get(Device, ep.device_id)
        if not device:
            continue
        sess = db.execute(
            select(BgpEvpnSession).where(BgpEvpnSession.device_id == device.id)
        ).scalar_one_or_none()
        if sess:
            bgp_sessions.append({
                "device_id": device.id,
                "device_name": device.name,
                "endpoint_label": ep.label,
                "peer_ip": sess.peer_ip,
                "state": sess.state.value,
                "routes_received": sess.routes_received,
                "routes_sent": sess.routes_sent,
            })

    next_hops = sorted({r["next_hop"] for r in route_rows if r.get("next_hop")})

    return {
        "source": "controller_rib",
        "vteps": vteps,
        "routes": route_rows,
        "route_count": len(route_rows),
        "next_hops": next_hops,
        "bgp_sessions": bgp_sessions,
        "note": (
            "控制面路由来自 Bugis 控制器 RIB；"
            "与设备 live BGP table 可能存在差异，请以现网对账为准。"
        ),
    }


def _compare_paths(
    computed_device_ids: list[int],
    probe_hops: list[dict],
    db: Session,
) -> dict:
    if not probe_hops:
        return {
            "status": "no_probe",
            "computed_device_ids": computed_device_ids,
            "probed_device_names": [],
            "note": "尚无拨测记录，仅展示 IGP 计算路径",
        }

    name_to_id: dict[str, int] = {}
    for did in computed_device_ids:
        dev = db.get(Device, did)
        if dev:
            name_to_id[dev.name] = did

    probed_names = [h.get("device") for h in probe_hops if h.get("device")]
    probed_ids: list[int] = []
    for name in probed_names:
        if name in name_to_id:
            probed_ids.append(name_to_id[name])

    if computed_device_ids == probed_ids:
        status = "match"
        note = "IGP 计算路径与最近一次拨测逐跳一致"
    elif probed_ids and set(probed_ids) == set(computed_device_ids):
        status = "partial"
        note = "拨测经过的设备与计算路径相同，但顺序或 ECMP 可能不同"
    elif probed_ids:
        status = "mismatch"
        note = (
            "拨测路径与 IGP 计算路径不一致；"
            "可能由 ECMP、策略路由或 SR-TE 导致"
        )
    else:
        status = "partial"
        note = "拨测结果无法与拓扑设备 ID 对齐"

    return {
        "status": status,
        "computed_device_ids": computed_device_ids,
        "probed_device_names": probed_names,
        "probed_device_ids": probed_ids,
        "note": note,
    }


def _enrich_segments(segments: list[dict], db: Session) -> list[dict]:
    out: list[dict] = []
    for seg in segments:
        row = dict(seg)
        from_dev = db.get(Device, seg["from_device_id"])
        to_dev = db.get(Device, seg["to_device_id"])
        row["from_device_name"] = from_dev.name if from_dev else None
        row["to_device_name"] = to_dev.name if to_dev else None
        out.append(row)
    return out


def _enrich_computed_hops(hops: list[dict], segments: list[dict]) -> list[dict]:
    seg_by_from = {s["from_device_id"]: s for s in segments if s.get("from_device_id")}
    out: list[dict] = []
    for i, hop in enumerate(hops):
        row = dict(hop)
        if i < len(hops) - 1:
            seg = seg_by_from.get(hop.get("device_id"))
            if seg:
                row["egress_interface"] = seg.get("interface")
                row["igp_cost"] = seg.get("igp_cost")
                row["cost_learned"] = seg.get("cost_learned")
                row["link_id"] = seg.get("link_id")
                row["link_name"] = seg.get("link_name")
        out.append(row)
    return out


def _merge_probe_segments(
    segments: list[dict],
    probe_hops: list[dict],
) -> list[dict]:
    if not probe_hops or not segments:
        return segments
    out: list[dict] = []
    for seg in segments:
        row = dict(seg)
        seq = seg.get("sequence")
        for h in probe_hops:
            hop_idx = h.get("hop")
            if hop_idx is not None and seq == hop_idx - 1:
                row["probe_segment_rtt_ms"] = h.get("segment_rtt_ms")
                row["probe_cumulative_rtt_ms"] = h.get("rtt_ms")
                row["probe_loss_pct"] = h.get("packet_loss_pct")
                row["probe_status"] = h.get("status")
                row["probe_source"] = h.get("device")
                row["probe_target"] = h.get("target")
                break
        out.append(row)
    return out


def _multipoint_underlay(db: Session, circuit: Circuit, eps: list[CircuitEndpoint]) -> dict:
    """Underlay view for multi-PE EVPN: highlight all access sites, no A→Z chain."""
    endpoint_devices: list[Device] = []
    endpoint_ids: list[int] = []
    hops: list[dict] = []
    for ep in eps:
        device = ep.device or db.get(Device, ep.device_id)
        if not device:
            continue
        endpoint_devices.append(device)
        endpoint_ids.append(device.id)
        hops.append({
            "device_id": device.id,
            "name": device.name,
            "hop_type": "access_pe",
            "endpoint_label": ep.label,
        })

    return {
        "path_mode": circuit.path_mode.value if circuit.path_mode else "auto",
        "path_reason": (
            f"多点 EVPN 接入 · {len(endpoint_ids)} 个 PE 站点共享 VNI {circuit.vni or '—'}；"
            "Underlay 展示全部接入 PE（非 A→Z 单路径）"
        ),
        "igp_algorithm": None,
        "total_igp_cost": None,
        "segment_list": [],
        "connectivity_errors": [],
        "computed": {
            "device_ids": endpoint_ids,
            "hops": hops,
            "segments": [],
        },
        "topology_highlight": {
            "mode": "multipoint",
            "device_ids": endpoint_ids,
            "link_ids": [],
            "endpoint_order": endpoint_ids,
        },
    }


def build_forwarding_path(db: Session, circuit: Circuit) -> dict:
    """Aggregate business, control, and underlay forwarding views."""
    eps = _ordered_endpoints(circuit)
    endpoint_ids = [ep.device_id for ep in eps]
    via_ids = [h.device_id for h in sorted(circuit.path_hops, key=lambda h: h.sequence)]
    multipoint = len(eps) > 2

    business_plane = _build_business_plane(db, circuit)
    topology_highlight: dict

    if multipoint:
        underlay_core = _multipoint_underlay(db, circuit, eps)
        preview = {
            "path_mode": underlay_core["path_mode"],
            "reason": underlay_core["path_reason"],
            "igp_algorithm": None,
            "total_igp_cost": None,
            "segment_list": [],
            "connectivity_errors": [],
        }
        computed_ids = underlay_core["computed"]["device_ids"]
        computed_hops = underlay_core["computed"]["hops"]
        segments: list[dict] = []
        link_ids: list[int] = []
        topology_highlight = underlay_core["topology_highlight"]
    else:
        if circuit.path_mode == PathMode.EXPLICIT_SR or via_ids:
            preview = path_service.preview_path(
                db, endpoint_ids, via_ids, PathMode.EXPLICIT_SR
            )
        else:
            preview = path_service.preview_path(db, endpoint_ids, None, PathMode.AUTO)

        chain_devices = path_service.build_device_chain(
            db, endpoint_ids, via_ids or None, circuit.path_mode
        )
        computed_ids = [d.id for d in chain_devices]
        segments = _enrich_segments(preview.get("segments") or [], db)
        computed_hops = _enrich_computed_hops(preview.get("hops") or [], segments)
        link_ids = [s["link_id"] for s in segments if s.get("link_id")]
        topology_highlight = {
            "mode": "point_to_point",
            "device_ids": computed_ids,
            "link_ids": link_ids,
            "endpoint_order": computed_ids,
        }

    latest = probe_log_service.latest_probe_log(db, circuit.id)
    probe_result = latest.result_json if latest else None
    probe_hops = (probe_result or {}).get("hops") or []
    if not multipoint:
        segments = _merge_probe_segments(segments, probe_hops)

    comparison = _compare_paths(computed_ids, probe_hops, db)

    probed_summary = None
    if probe_result:
        probed_summary = {
            "available": True,
            "probe_log_id": latest.id if latest else None,
            "probed_at": latest.created_at.isoformat() if latest and latest.created_at else None,
            "mode": probe_result.get("mode"),
            "probe_method": probe_result.get("probe_method"),
            "reachable": probe_result.get("reachable"),
            "rtt_ms": probe_result.get("rtt_ms"),
            "jitter_ms": probe_result.get("jitter_ms"),
            "packet_loss_pct": probe_result.get("packet_loss_pct"),
            "hop_count": probe_result.get("hop_count"),
            "hops": probe_hops,
            "service_plane": probe_result.get("service_plane"),
            "fabric": probe_result.get("fabric"),
        }
    else:
        probed_summary = {
            "available": False,
            "note": "尚无拨测记录；可执行「拨测」获取 Underlay 实测数据",
        }

    return {
        "circuit_id": circuit.id,
        "circuit_code": circuit.code,
        "path_mode": circuit.path_mode.value if circuit.path_mode else "auto",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "business_plane": business_plane,
        "control_plane": _build_control_plane(db, circuit),
        "underlay": {
            "topology_mode": "multipoint" if multipoint else "point_to_point",
            "path_mode": preview.get("path_mode"),
            "path_reason": preview.get("reason"),
            "igp_algorithm": preview.get("igp_algorithm"),
            "total_igp_cost": preview.get("total_igp_cost"),
            "segment_list": preview.get("segment_list") or [],
            "connectivity_errors": preview.get("connectivity_errors") or [],
            "computed": {
                "device_ids": computed_ids,
                "hops": computed_hops,
                "segments": segments,
            },
            "probed": probed_summary,
            "comparison": comparison,
            "topology_highlight": topology_highlight,
        },
    }
