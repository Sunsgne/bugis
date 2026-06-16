"""Seed the platform with demo sites, tenants, devices and circuits.

Run from the backend directory:  python -m scripts.seed
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import (  # noqa: E402
    ensure_platform_settings,
    ensure_snmp_settings,
    ensure_superuser,
    ensure_tenant_portal_demo_user,
)
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.models.circuit import Circuit, CircuitEndpoint  # noqa: E402
from app.models.controller import Controller  # noqa: E402
from app.models.device import Device  # noqa: E402
from app.models.enums import (  # noqa: E402
    CircuitStatus,
    ControllerType,
    DeliveryMode,
    DeviceRole,
    DeviceStatus,
    LinkType,
    OverlayTech,
    ServiceType,
    TenantType,
    Vendor,
)
from app.models.link import Link  # noqa: E402
from app.models.site import Site  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.services import allocation  # noqa: E402


def run() -> None:
    init_db()
    db = SessionLocal()
    try:
        ensure_superuser(db)
        ensure_snmp_settings(db)
        ensure_platform_settings(db)
        if db.query(Site).count() > 0:
            print("Data already seeded; skipping.")
            return

        # --- Controllers ---
        # Built-in self-developed Bugis SDN controller (no market dependency).
        bugis_ctrl = Controller(
            name="Bugis SDN 控制器", type=ControllerType.BUGIS,
            base_url="internal://bugis", username="-",
            description="内置自研 EVPN 控制平面 + 南向编排，托管广州 Fabric")
        db.add(bugis_ctrl)
        db.flush()

        # --- Sites / DCs ---
        bj = Site(name="北京数据中心", code="BJ-DC1", region="华北",
                  bgp_asn=65001, underlay_prefix="10.1.0.0/16")
        sh = Site(name="上海数据中心", code="SH-DC1", region="华东",
                  bgp_asn=65002, underlay_prefix="10.2.0.0/16")
        gz = Site(name="广州数据中心", code="GZ-DC1", region="华南",
                  bgp_asn=65003, underlay_prefix="10.3.0.0/16",
                  delivery_mode=DeliveryMode.CONTROLLER, controller_id=bugis_ctrl.id)
        db.add_all([bj, sh, gz])
        db.flush()

        # --- Devices ---
        devices = [
            Device(name="BJ-LEAF-01", vendor=Vendor.H3C, model="S6850",
                   role=DeviceRole.LEAF, overlay_tech=OverlayTech.VXLAN_EVPN,
                   status=DeviceStatus.ONLINE, mgmt_ip="10.1.0.11",
                   loopback_ip="10.1.255.11", bgp_asn=65001, site_id=bj.id),
            Device(name="BJ-BORDER-01", vendor=Vendor.HUAWEI, model="CE12800",
                   role=DeviceRole.DCI_GW, overlay_tech=OverlayTech.VXLAN_EVPN,
                   status=DeviceStatus.ONLINE, mgmt_ip="10.1.0.1",
                   loopback_ip="10.1.255.1", bgp_asn=65001,
                   is_route_reflector=True, site_id=bj.id),
            Device(name="SH-LEAF-01", vendor=Vendor.HUAWEI, model="CE6881",
                   role=DeviceRole.LEAF, overlay_tech=OverlayTech.VXLAN_EVPN,
                   status=DeviceStatus.ONLINE, mgmt_ip="10.2.0.11",
                   loopback_ip="10.2.255.11", bgp_asn=65002, site_id=sh.id),
            Device(name="SH-PE-01", vendor=Vendor.CISCO, model="NCS-540",
                   role=DeviceRole.PE, overlay_tech=OverlayTech.SRMPLS_EVPN,
                   status=DeviceStatus.ONLINE, mgmt_ip="10.2.0.21",
                   loopback_ip="10.2.255.21", bgp_asn=65002, sr_node_sid=21,
                   site_id=sh.id),
            Device(name="SH-BORDER-01", vendor=Vendor.CISCO, model="ASR-9000",
                   role=DeviceRole.DCI_GW, overlay_tech=OverlayTech.SRMPLS_EVPN,
                   status=DeviceStatus.ONLINE, mgmt_ip="10.2.0.1",
                   loopback_ip="10.2.255.1", bgp_asn=65002, sr_node_sid=1,
                   is_route_reflector=True, site_id=sh.id),
            Device(name="GZ-PE-01", vendor=Vendor.JUNIPER, model="MX204",
                   role=DeviceRole.PE, overlay_tech=OverlayTech.SRMPLS_EVPN,
                   status=DeviceStatus.ONLINE, mgmt_ip="10.3.0.21",
                   loopback_ip="10.3.255.21", bgp_asn=65003, sr_node_sid=121,
                   site_id=gz.id),
            Device(name="GZ-LEAF-01", vendor=Vendor.ARISTA, model="7280R3",
                   role=DeviceRole.LEAF, overlay_tech=OverlayTech.SRMPLS_EVPN,
                   status=DeviceStatus.ONLINE, mgmt_ip="10.3.0.11",
                   loopback_ip="10.3.255.11", bgp_asn=65003, sr_node_sid=111,
                   site_id=gz.id),
            Device(name="GZ-WHITEBOX-01", vendor=Vendor.FRR, model="SONiC+FRR",
                   role=DeviceRole.LEAF, overlay_tech=OverlayTech.VXLAN_EVPN,
                   status=DeviceStatus.ONLINE, mgmt_ip="10.3.0.31",
                   loopback_ip="10.3.255.31", bgp_asn=65003, site_id=gz.id),
        ]
        db.add_all(devices)
        db.flush()
        by_name = {d.name: d for d in devices}

        # Interfaces are populated on demand via SNMP discovery
        # (POST /devices/{id}/discover-interfaces), so we don't pre-seed them.

        # --- Tenants ---
        t_bank = Tenant(name="某股份制银行", code="BANK01",
                        type=TenantType.ENTERPRISE, contact_name="张经理")
        t_cloud = Tenant(name="云科技公司", code="CLOUD01",
                         type=TenantType.HYBRID_CLOUD, contact_name="李工",
                         cloud_account="aws-acct-12345")
        t_gov = Tenant(name="智慧政务平台", code="GOV01",
                       type=TenantType.PUBLIC_CLOUD, contact_name="王主任")
        db.add_all([t_bank, t_cloud, t_gov])
        db.flush()

        # --- Circuits ---
        def make_circuit(name, tenant, service_type, eps, bw, sla="99.95"):
            c = Circuit(name=name, code=allocation.next_circuit_code(db),
                        tenant_id=tenant.id, service_type=service_type,
                        bandwidth_mbps=bw, sla_target=sla, mtu=9000,
                        status=CircuitStatus.DRAFT)
            db.add(c)
            db.flush()
            endpoints = []
            for label, dev_name, iface in eps:
                ep = CircuitEndpoint(
                    circuit_id=c.id, device_id=by_name[dev_name].id,
                    label=label, interface_name=iface,
                    gateway_ip="192.168.10.1" if label == "A" else None)
                db.add(ep)
                endpoints.append(ep)
            db.flush()
            allocation.auto_allocate_circuit_fields(db, c, tenant_asn(eps))
            return c

        def tenant_asn(eps):
            for _, dev_name, _ in eps:
                d = by_name[dev_name]
                if d.bgp_asn:
                    return d.bgp_asn
            return 65000

        c_bank = make_circuit("银行北京-上海二层专线", t_bank, ServiceType.L2VPN_EVPN,
                     [("A", "BJ-LEAF-01", "GE1/0/1"),
                      ("Z", "SH-LEAF-01", "GE1/0/1")], 1000)
        c_cloud = make_circuit("云公司混合云三层互联", t_cloud, ServiceType.L3VPN_EVPN,
                     [("A", "SH-PE-01", "GE1/0/2"),
                      ("Z", "GZ-PE-01", "GE1/0/2")], 2000)
        make_circuit("政务DCI数据中心互联", t_gov, ServiceType.DCI,
                     [("A", "BJ-BORDER-01", "GE1/0/3"),
                      ("Z", "SH-BORDER-01", "GE1/0/3")], 5000, sla="99.99")

        # Demo: keep two circuits active so monitoring / traffic pages have data.
        c_bank.status = CircuitStatus.ACTIVE
        c_cloud.status = CircuitStatus.ACTIVE

        # Remote IPT demo: bank in CN accesses US public internet via SH egress
        c_ript = Circuit(
            name="openai-azure", code=allocation.next_circuit_code(db),
            tenant_id=t_bank.id, service_type=ServiceType.REMOTE_IPT,
            bandwidth_mbps=200, sla_target="99.9", mtu=1500,
            status=CircuitStatus.DECOMMISSIONED,
            egress_country="US", egress_site_id=sh.id,
            description="通过专线使用美国公网访问 Azure/OpenAI",
        )
        db.add(c_ript)
        db.flush()
        db.add(CircuitEndpoint(
            circuit_id=c_ript.id, device_id=by_name["BJ-LEAF-01"].id,
            label="A", interface_name="GE1/0/10",
            gateway_ip="10.200.1.1", vlan_id=200,
        ))
        db.flush()
        allocation.auto_allocate_circuit_fields(db, c_ript, 65001)

        # --- DCI / intra-DC links (capacity & topology) ---
        db.add_all([
            Link(name="BJ<->SH DCI", type=LinkType.DCI,
                 device_a_id=by_name["BJ-BORDER-01"].id,
                 device_z_id=by_name["SH-BORDER-01"].id,
                 interface_a="HundredGE1/0/1", interface_z="HundredGE0/0/1",
                 capacity_mbps=100000, reserved_mbps=6000),
            Link(name="SH<->GZ DCI", type=LinkType.DCI,
                 device_a_id=by_name["SH-BORDER-01"].id,
                 device_z_id=by_name["GZ-PE-01"].id,
                 interface_a="HundredGE0/0/2", interface_z="et-0/0/0",
                 capacity_mbps=100000, reserved_mbps=2000),
            Link(name="BJ leaf-border", type=LinkType.INTRA_DC,
                 device_a_id=by_name["BJ-LEAF-01"].id,
                 device_z_id=by_name["BJ-BORDER-01"].id,
                 capacity_mbps=40000, reserved_mbps=1000),
            Link(name="SH leaf-border", type=LinkType.INTRA_DC,
                 device_a_id=by_name["SH-LEAF-01"].id,
                 device_z_id=by_name["SH-BORDER-01"].id,
                 capacity_mbps=40000, reserved_mbps=1000),
            Link(name="GZ leaf-pe", type=LinkType.INTRA_DC,
                 device_a_id=by_name["GZ-LEAF-01"].id,
                 device_z_id=by_name["GZ-PE-01"].id,
                 capacity_mbps=40000, reserved_mbps=2000),
        ])

        from app.services import link_monitor, snmp

        for d in devices:
            snmp.discover_interfaces(db, d)
        link_monitor.sync_all_link_capacity(db)

        ensure_tenant_portal_demo_user(db)

        db.commit()
        print("Seed complete:")
        print(f"  sites={db.query(Site).count()} "
              f"tenants={db.query(Tenant).count()} "
              f"devices={db.query(Device).count()} "
              f"circuits={db.query(Circuit).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
