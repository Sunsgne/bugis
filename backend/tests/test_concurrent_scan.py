"""Tests for parallel device inventory scans."""
from __future__ import annotations

import itertools

from app.core.database import SessionLocal
from app.models.device import Device, DeviceInterface
from app.models.enums import Vendor
from app.services import concurrent_scan, port_inventory

_seq = itertools.count(1)


def test_scan_devices_parallel_updates_all_ports():
    db = SessionLocal()
    try:
        devices: list[Device] = []
        for _ in range(2):
            n = next(_seq)
            dev = Device(name=f"PAR-{n}", vendor=Vendor.H3C, mgmt_ip=f"10.88.{n}.1")
            db.add(dev)
            db.flush()
            db.add(
                DeviceInterface(
                    device_id=dev.id,
                    name=f"GE1/0/{n}",
                    used_s_vids=[
                        {
                            "s_vid": 100 + n,
                            "access_mode": "dot1q",
                            "source": "device",
                        }
                    ],
                    allocated=True,
                )
            )
            devices.append(dev)
        db.commit()

        concurrent_scan.scan_devices_parallel([d.id for d in devices])

        for dev in devices:
            db.refresh(dev)
            result = port_inventory.list_port_bindings(db, dev)
            assert result["device_only_bindings"] == 1
    finally:
        db.close()
