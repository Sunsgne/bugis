"""Shared demo data: tenants, circuits, links."""
from __future__ import annotations

from sqlalchemy.orm import Session

from sqlalchemy.orm import joinedload

from app.models.circuit import Circuit, CircuitEndpoint
from app.models.controlplane import EvpnRoute
from app.models.device import Device
from app.models.enums import CircuitStatus, LinkType, ServiceType, TenantType
from app.models.link import Link
from app.models.site import Site
from app.models.tenant import Tenant
from app.services import allocation


def _devices_by_name(db: Session) -> dict[str, Device]:
    return {d.name: d for d in db.query(Device).all()}


def ensure_demo_tenants(db: Session) -> dict[str, Tenant]:
    by_code = {t.code: t for t in db.query(Tenant).all()}
    defaults = [
        ("BANK01", Tenant(name="某股份制银行", code="BANK01",
                          type=TenantType.ENTERPRISE, contact_name="张经理")),
        ("CLOUD01", Tenant(name="云科技公司", code="CLOUD01",
                           type=TenantType.HYBRID_CLOUD, contact_name="李工",
                           cloud_account="aws-acct-12345")),
        ("GOV01", Tenant(name="智慧政务平台", code="GOV01",
                         type=TenantType.PUBLIC_CLOUD, contact_name="王主任")),
    ]
    for code, tenant in defaults:
        if code not in by_code:
            db.add(tenant)
            db.flush()
            by_code[code] = tenant
    return by_code


def _tenant_asn(by_name: dict[str, Device], eps: list[tuple[str, str, str]]) -> int:
    for _, dev_name, _ in eps:
        d = by_name.get(dev_name)
        if d and d.bgp_asn:
            return d.bgp_asn
    return 65000


def _make_circuit(
    db: Session,
    by_name: dict[str, Device],
    *,
    name: str,
    tenant: Tenant,
    service_type: ServiceType,
    eps: list[tuple[str, str, str]],
    bw: int,
    sla: str = "99.95",
    status: CircuitStatus = CircuitStatus.DRAFT,
) -> Circuit | None:
    missing = [n for _, n, _ in eps if n not in by_name]
    if missing:
        return None
    c = Circuit(
        name=name,
        code=allocation.next_circuit_code(db),
        tenant_id=tenant.id,
        service_type=service_type,
        bandwidth_mbps=bw,
        sla_target=sla,
        mtu=9000,
        status=status,
    )
    db.add(c)
    db.flush()
    for label, dev_name, iface in eps:
        db.add(
            CircuitEndpoint(
                circuit_id=c.id,
                device_id=by_name[dev_name].id,
                label=label,
                interface_name=iface,
                gateway_ip="192.168.10.1" if label == "A" else None,
            )
        )
    db.flush()
    allocation.auto_allocate_circuit_fields(db, c, _tenant_asn(by_name, eps))
    return c


def backfill_demo_circuits(db: Session) -> int:
    """Create demo circuits when the platform has devices but no circuits."""
    if db.query(Circuit).count() > 0:
        return 0

    by_name = _devices_by_name(db)
    need = {"BJ-LEAF-01", "SH-LEAF-01", "BJ-BORDER-01", "SH-BORDER-01"}
    if not need.issubset(by_name):
        print(f"Skip circuit backfill: missing devices {sorted(need - by_name.keys())}")
        return 0

    tenants = ensure_demo_tenants(db)

    created = 0
    specs = [
        ("银行北京-上海二层专线", "BANK01", ServiceType.L2VPN_EVPN,
         [("A", "BJ-LEAF-01", "GE1/0/1"), ("Z", "SH-LEAF-01", "GE1/0/1")], 1000, "99.95", CircuitStatus.ACTIVE),
        ("云公司混合云三层互联", "CLOUD01", ServiceType.L3VPN_EVPN,
         [("A", "SH-PE-01", "GE1/0/2"), ("Z", "GZ-PE-01", "GE1/0/2")], 2000, "99.95", CircuitStatus.ACTIVE),
        ("政务DCI数据中心互联", "GOV01", ServiceType.DCI,
         [("A", "BJ-BORDER-01", "GE1/0/3"), ("Z", "SH-BORDER-01", "GE1/0/3")], 5000, "99.99", CircuitStatus.DRAFT),
    ]
    for name, tcode, stype, eps, bw, sla, status in specs:
        if _make_circuit(db, by_name, name=name, tenant=tenants[tcode], service_type=stype,
                         eps=eps, bw=bw, sla=sla, status=status):
            created += 1

    if db.query(Link).count() == 0 and {"BJ-BORDER-01", "SH-BORDER-01", "GZ-PE-01", "GZ-LEAF-01"}.issubset(by_name):
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

    sh_site = db.query(Site).filter(Site.code == "SH-DC1").first()
    if sh_site and "BJ-LEAF-01" in by_name:
        c_ript = Circuit(
            name="openai-azure",
            code=allocation.next_circuit_code(db),
            tenant_id=tenants["BANK01"].id,
            service_type=ServiceType.REMOTE_IPT,
            bandwidth_mbps=200,
            sla_target="99.9",
            mtu=1500,
            status=CircuitStatus.DECOMMISSIONED,
            egress_country="US",
            egress_site_id=sh_site.id,
            description="通过专线使用美国公网访问 Azure/OpenAI",
        )
        db.add(c_ript)
        db.flush()
        db.add(
            CircuitEndpoint(
                circuit_id=c_ript.id,
                device_id=by_name["BJ-LEAF-01"].id,
                label="A",
                interface_name="GE1/0/10",
                gateway_ip="10.200.1.1",
                vlan_id=200,
            )
        )
        db.flush()
        allocation.auto_allocate_circuit_fields(db, c_ript, 65001)
        created += 1

    db.commit()
    return created


def sync_active_circuit_controlplane(db: Session) -> int:
    """Install EVPN RIB entries for active circuits missing controller state."""
    from app.controller.engine import controller

    active = (
        db.query(Circuit)
        .options(joinedload(Circuit.endpoints).joinedload(CircuitEndpoint.device))
        .filter(Circuit.status == CircuitStatus.ACTIVE)
        .all()
    )
    synced = 0
    for circuit in active:
        has_routes = (
            db.query(EvpnRoute.id)
            .filter(EvpnRoute.circuit_id == circuit.id)
            .first()
            is not None
        )
        if has_routes:
            continue
        endpoints = [ep for ep in circuit.endpoints if ep.device]
        if not endpoints:
            continue
        if circuit.vni is None:
            by_name = {ep.device.name: ep.device for ep in endpoints if ep.device}
            eps_spec = [(ep.label, ep.device.name, ep.interface_name) for ep in endpoints]
            allocation.auto_allocate_circuit_fields(
                db, circuit, _tenant_asn(by_name, eps_spec)
            )
        controller.install_circuit(db, circuit, endpoints)
        synced += 1
    if synced:
        db.commit()
    return synced


def activate_draft_circuits(db: Session, limit: int = 2) -> int:
    active = db.query(Circuit).filter(Circuit.status == CircuitStatus.ACTIVE).count()
    if active > 0:
        return 0
    drafts = (
        db.query(Circuit)
        .filter(Circuit.status == CircuitStatus.DRAFT)
        .order_by(Circuit.id)
        .limit(limit)
        .all()
    )
    for c in drafts:
        c.status = CircuitStatus.ACTIVE
    if drafts:
        db.commit()
    return len(drafts)
