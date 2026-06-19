"""Tests for alarm notification context enrichment."""
from __future__ import annotations

import pytest

from app.core.database import SessionLocal
from app.models.enums import AccessMode, ServiceType
from app.services import alarm_messages as msg
from app.services.alarm_context import circuit_alarm_context, link_alarm_context
from app.services.alarm_template_registry import get_templates, merge_templates


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_circuit_alarm_context_includes_endpoints(db_session):
    from app.models.circuit import Circuit, CircuitEndpoint
    from app.models.device import Device
    from app.models.enums import DeviceRole, OverlayTech, Vendor
    from app.models.site import Site
    from app.models.tenant import Tenant

    site = Site(name="DC", code="DC1", bgp_asn=65001)
    tenant = Tenant(name="Acme Corp", code="ACME", type="enterprise")
    dev_a = Device(
        name="PE-A", vendor=Vendor.H3C, role=DeviceRole.LEAF,
        overlay_tech=OverlayTech.VXLAN_EVPN, mgmt_ip="10.1.1.1", site=site,
    )
    dev_z = Device(
        name="PE-Z", vendor=Vendor.H3C, role=DeviceRole.LEAF,
        overlay_tech=OverlayTech.VXLAN_EVPN, mgmt_ip="10.1.1.2", site=site,
    )
    circuit = Circuit(
        name="svc-1", code="CIR-CTX", tenant=tenant,
        service_type=ServiceType.L2VPN_EVPN, bandwidth_mbps=500,
    )
    circuit.endpoints = [
        CircuitEndpoint(
            label="A", device=dev_a, interface_name="GE1/0/1",
            access_mode=AccessMode.DOT1Q, vlan_id=100,
        ),
        CircuitEndpoint(
            label="Z", device=dev_z, interface_name="GE1/0/2",
            access_mode=AccessMode.DOT1Q, vlan_id=100,
        ),
    ]
    db_session.add_all([site, tenant, dev_a, dev_z, circuit])
    db_session.flush()

    ctx = circuit_alarm_context(db_session, circuit)
    assert ctx["tenant_name"] == "Acme Corp"
    assert ctx["endpoint_a_device"] == "PE-A"
    assert ctx["endpoint_a_svid"] == "S-VID 100"
    assert "PE-Z" in ctx["endpoint_summary"]

    templates = merge_templates(None)
    copy = msg.build_circuit_tunnel_down(
        circuit.code, "degraded", templates,
        **{k: v for k, v in ctx.items() if k != "circuit_code"},
    )
    assert "Acme Corp" in copy.detail
    assert "PE-A" in copy.detail
    assert "S-VID 100" in copy.detail


def test_link_alarm_context_includes_supplier(db_session):
    from app.models.device import Device
    from app.models.enums import DeviceRole, LinkType, OverlayTech, Vendor
    from app.models.link import Link
    from app.models.site import Site

    site = Site(name="DC", code="DC2", bgp_asn=65002)
    dev_a = Device(
        name="GW-A", vendor=Vendor.H3C, role=DeviceRole.DCI_GW,
        overlay_tech=OverlayTech.VXLAN_EVPN, mgmt_ip="10.2.1.1", site=site,
    )
    dev_z = Device(
        name="GW-Z", vendor=Vendor.H3C, role=DeviceRole.DCI_GW,
        overlay_tech=OverlayTech.VXLAN_EVPN, mgmt_ip="10.2.1.2", site=site,
    )
    link = Link(
        name="HK-SG-01", type=LinkType.DCI,
        device_a_id=dev_a.id, device_z_id=dev_z.id,
        interface_a="Hu1/0/49", interface_z="Hu1/0/49",
        supplier="Telstra", capacity_mbps=100000,
    )
    db_session.add_all([site, dev_a, dev_z])
    db_session.flush()
    link.device_a_id = dev_a.id
    link.device_z_id = dev_z.id
    db_session.add(link)
    db_session.flush()

    ctx = link_alarm_context(db_session, link)
    assert ctx["supplier"] == "Telstra"
    assert ctx["device_a_name"] == "GW-A"
    assert "Hu1/0/49" in ctx["endpoint_summary"]

    copy = msg.build_link_utilization(
        link.name, 90.0, 85.0,
        capacity_mbps=100000, traffic_mbps=90000.0,
        templates=get_templates(db_session),
        **{k: v for k, v in ctx.items() if k not in ("link_name", "util_pct", "threshold_pct", "cap_display", "traffic_display")},
    )
    assert "Telstra" in copy.detail
    assert "GW-A" in copy.detail
