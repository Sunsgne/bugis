"""Failed circuits must keep platform port/SVI association in inventory."""
from __future__ import annotations

import uuid

from app.core.database import SessionLocal
from app.models.circuit import Circuit, CircuitEndpoint
from app.models.device import Device, DeviceInterface
from app.models.enums import AccessMode, CircuitStatus, ServiceType, Vendor
from app.models.tenant import Tenant
from app.services import port_inventory


def test_failed_circuit_reserves_platform_svid_in_scan():
    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        tenant = Tenant(name=f"T {suffix}", code=f"T{suffix}")
        device = Device(name=f"PE-{suffix}", vendor=Vendor.H3C, mgmt_ip="10.0.0.1")
        db.add_all([tenant, device])
        db.flush()
        circuit = Circuit(
            name="Failed line",
            code=f"C-FAIL-{suffix}",
            tenant_id=tenant.id,
            service_type=ServiceType.L2VPN_EVPN,
            status=CircuitStatus.FAILED,
            vni=31000,
            vsi_name=f"vsi_fail_{suffix}",
            bandwidth_mbps=100,
        )
        db.add(circuit)
        db.flush()
        db.add(
            CircuitEndpoint(
                circuit_id=circuit.id,
                device_id=device.id,
                label="A",
                interface_name="GE1/0/10",
                access_mode=AccessMode.DOT1Q,
                vlan_id=2001,
            )
        )
        db.add(
            DeviceInterface(
                device_id=device.id,
                name="GE1/0/10",
                used_s_vids=[
                    {
                        "s_vid": 2001,
                        "c_vid": None,
                        "access_mode": "dot1q",
                        "source": "device",
                        "vsi_name": circuit.vsi_name,
                        "vni": circuit.vni,
                    }
                ],
                allocated=True,
            )
        )
        db.commit()

        port_inventory.scan_device(db, device)
        db.commit()
        db.refresh(device)
        iface = db.query(DeviceInterface).filter(
            DeviceInterface.device_id == device.id
        ).one()
        platform_rows = [
            e for e in (iface.used_s_vids or [])
            if e.get("source") == "platform" and e.get("s_vid") == 2001
        ]
        assert platform_rows, iface.used_s_vids
        assert platform_rows[0].get("circuit_code") == circuit.code

        bindings = port_inventory.list_port_bindings(db, device)
        row = next(i for i in bindings["items"] if i["s_vid"] == 2001)
        assert row["binding_type"] == "platform"
        assert row["circuit_code"] == circuit.code
    finally:
        db.rollback()
        db.close()
