"""Unit tests for multipoint EVPN forwarding path."""
from __future__ import annotations

from types import SimpleNamespace

from app.models.enums import AccessMode, OverlayTech, ServiceType
from app.services import forwarding_path_service as fps


def test_build_business_plane_multipoint(monkeypatch):
    monkeypatch.setattr(fps, "_find_access_binding_for_endpoint", lambda *a, **k: None)
    circuit = SimpleNamespace(
        service_type=ServiceType.L2VPN_EVPN,
        vni=30007,
        vsi_name="vsi-30007",
        route_distinguisher="65000:30007",
        route_target="65000:30007",
        endpoints=[
            SimpleNamespace(
                id=1, label="A", device_id=1, interface_name="GE1/0/1",
                vlan_id=3005, inner_vlan_id=None, access_mode=AccessMode.DOT1Q,
                device=SimpleNamespace(id=1, name="PE-A", loopback_ip="10.0.0.1", overlay_tech=OverlayTech.VXLAN_EVPN),
            ),
            SimpleNamespace(
                id=2, label="C", device_id=2, interface_name="GE1/0/2",
                vlan_id=3005, inner_vlan_id=None, access_mode=AccessMode.DOT1Q,
                device=SimpleNamespace(id=2, name="PE-C", loopback_ip="10.0.0.2", overlay_tech=OverlayTech.VXLAN_EVPN),
            ),
            SimpleNamespace(
                id=3, label="Z", device_id=3, interface_name="GE1/0/3",
                vlan_id=3005, inner_vlan_id=None, access_mode=AccessMode.DOT1Q,
                device=SimpleNamespace(id=3, name="PE-Z", loopback_ip="10.0.0.3", overlay_tech=OverlayTech.VXLAN_EVPN),
            ),
        ],
    )

    bp = fps._build_business_plane(None, circuit)  # type: ignore[arg-type]

    assert bp["topology"] == "multipoint"
    assert bp["endpoint_count"] == 3
    assert len(bp["endpoints"]) == 3
    layers = [h["layer"] for h in bp["hops"]]
    assert "evpn_tunnel" not in layers
    assert layers[-1] == "evpn_instance"


def test_multipoint_underlay_lists_all_pe():
    circuit = SimpleNamespace(
        path_mode=SimpleNamespace(value="auto"),
        vni=30007,
    )
    eps = [
        SimpleNamespace(label="A", device_id=1, device=SimpleNamespace(id=1, name="PE-A")),
        SimpleNamespace(label="C", device_id=2, device=SimpleNamespace(id=2, name="PE-C")),
        SimpleNamespace(label="D", device_id=3, device=SimpleNamespace(id=3, name="PE-D")),
        SimpleNamespace(label="Z", device_id=4, device=SimpleNamespace(id=4, name="PE-Z")),
    ]

    ul = fps._multipoint_underlay(None, circuit, eps)  # type: ignore[arg-type]

    assert ul["topology_highlight"]["mode"] == "multipoint"
    assert ul["computed"]["device_ids"] == [1, 2, 3, 4]
    assert len(ul["computed"]["hops"]) == 4
    assert ul["computed"]["segments"] == []
