"""Northbound delegation to SDN / vendor fabric controllers.

Instead of pushing CLI/NETCONF to each device, the platform can hand a
normalized service intent to a controller's northbound REST API. Each
controller type maps the intent to a representative endpoint + payload.

In dry-run mode the request is rendered (method/url/json) but not sent.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from app.models.circuit import Circuit, CircuitEndpoint
from app.models.controller import Controller
from app.models.enums import ControllerType, ServiceType


@dataclass
class ControllerRequest:
    method: str
    url: str
    payload: dict

    def render(self) -> str:
        return (
            f"{self.method} {self.url}\n"
            f"Content-Type: application/json\n\n"
            f"{json.dumps(self.payload, ensure_ascii=False, indent=2)}"
        )


def _base_intent(circuit: Circuit, endpoints: list[CircuitEndpoint],
                 devices: dict[int, str]) -> dict:
    return {
        "name": circuit.code,
        "description": circuit.name,
        "serviceType": circuit.service_type.value,
        "vni": circuit.vni,
        "vlan": circuit.vlan_id,
        "routeDistinguisher": circuit.route_distinguisher,
        "routeTarget": circuit.route_target,
        "vrf": circuit.vrf_name,
        "bandwidthMbps": circuit.bandwidth_mbps,
        "mtu": circuit.mtu,
        "endpoints": [
            {
                "device": devices.get(ep.device_id, ep.device_id),
                "interface": ep.interface_name,
                "vlan": ep.vlan_id or circuit.vlan_id,
                "gateway": ep.gateway_ip,
            }
            for ep in endpoints
        ],
    }


def build_request(
    controller: Controller,
    circuit: Circuit,
    endpoints: list[CircuitEndpoint],
    devices: dict[int, str],
    operation: str,
) -> ControllerRequest:
    intent = _base_intent(circuit, endpoints, devices)
    base = controller.base_url.rstrip("/")
    method = "DELETE" if operation == "remove" else "POST"

    if controller.type == ControllerType.NCE_FABRIC:
        # Huawei iMaster NCE-Fabric northbound (representative path).
        is_l3 = circuit.service_type in (ServiceType.L3VPN_EVPN, ServiceType.DCI)
        kind = "vpc-connections" if is_l3 else "logical-switchs"
        url = f"{base}/restconf/v2/data/huawei-nce-fabric:{kind}"
        payload = {"fabric-service": intent}
    elif controller.type == ControllerType.SEERENGINE:
        # H3C AD-DC SeerEngine northbound (representative path).
        url = f"{base}/sdn/v2.0/tenants/{circuit.tenant_id}/networks"
        payload = {"network": intent}
    elif controller.type == ControllerType.OPENDAYLIGHT:
        url = (
            f"{base}/restconf/config/network-topology:network-topology/"
            f"topology/ovsdb:1/evpn/{circuit.vni}"
        )
        payload = {"evpn-instance": intent}
    else:  # ONOS
        url = f"{base}/onos/v1/evpn/instances/{circuit.vni}"
        payload = {"evpnInstance": intent}

    if method == "DELETE":
        url = f"{url}/{circuit.code}"
    return ControllerRequest(method=method, url=url, payload=payload)


def deliver(controller: Controller, req: ControllerRequest, dry_run: bool = True) -> dict:
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "output": f"[DRY-RUN] controller={controller.type.value} "
            f"({controller.name})\n{req.render()}",
        }
    try:  # pragma: no cover - requires live controller
        import httpx

        with httpx.Client(verify=bool(controller.verify_tls), timeout=30) as client:
            auth = None
            if controller.username:
                auth = (controller.username, controller.password or "")
            resp = client.request(req.method, req.url, json=req.payload, auth=auth)
            return {
                "success": resp.is_success,
                "dry_run": False,
                "output": f"{resp.status_code} {resp.text[:2000]}",
            }
    except Exception as exc:  # pragma: no cover
        return {"success": False, "dry_run": False, "output": f"controller error: {exc}"}
