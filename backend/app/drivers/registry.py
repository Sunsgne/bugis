"""Driver registry mapping vendors to driver instances."""
from __future__ import annotations

from app.drivers.base import BaseDriver
from app.drivers.vendors import (
    AristaDriver,
    CiscoDriver,
    FRRDriver,
    H3CDriver,
    HuaweiDriver,
    JuniperDriver,
)
from app.models.enums import Vendor

_DRIVERS: dict[Vendor, BaseDriver] = {
    Vendor.H3C: H3CDriver(),
    Vendor.HUAWEI: HuaweiDriver(),
    Vendor.JUNIPER: JuniperDriver(),
    Vendor.ARISTA: AristaDriver(),
    Vendor.CISCO: CiscoDriver(),
    Vendor.FRR: FRRDriver(),
}


def get_driver(vendor: Vendor) -> BaseDriver:
    driver = _DRIVERS.get(vendor)
    if driver is None:
        raise ValueError(f"No driver registered for vendor: {vendor}")
    return driver


def list_drivers() -> dict[str, dict[str, str]]:
    return {
        v.value: {
            "vendor": d.vendor.value,
            "overlay_tech": d.overlay_tech.value,
            "transport": d.transport,
        }
        for v, d in _DRIVERS.items()
    }
