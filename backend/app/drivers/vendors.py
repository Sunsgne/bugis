"""Concrete vendor driver implementations.

The vendor split follows the platform's design:
  * H3C / Huawei      -> BGP EVPN VXLAN  (NETCONF / Comware / VRP)
  * Juniper / Arista / Cisco -> SR-MPLS EVPN (NETCONF / CLI)
"""
from __future__ import annotations

from app.drivers.base import BaseDriver
from app.models.enums import OverlayTech, Vendor


class H3CDriver(BaseDriver):
    vendor = Vendor.H3C
    overlay_tech = OverlayTech.VXLAN_EVPN
    template_dir = "h3c"
    transport = "netconf"


class HuaweiDriver(BaseDriver):
    vendor = Vendor.HUAWEI
    overlay_tech = OverlayTech.VXLAN_EVPN
    template_dir = "huawei"
    transport = "netconf"


class JuniperDriver(BaseDriver):
    vendor = Vendor.JUNIPER
    overlay_tech = OverlayTech.SRMPLS_EVPN
    template_dir = "juniper"
    transport = "netconf"


class AristaDriver(BaseDriver):
    vendor = Vendor.ARISTA
    overlay_tech = OverlayTech.SRMPLS_EVPN
    template_dir = "arista"
    transport = "cli"


class CiscoDriver(BaseDriver):
    vendor = Vendor.CISCO
    overlay_tech = OverlayTech.SRMPLS_EVPN
    template_dir = "cisco"
    transport = "netconf"
