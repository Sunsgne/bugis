"""Path service unit tests."""
from app.models.device import Device
from app.models.enums import OverlayTech, Vendor
from app.services.bw_parser import parse_bw_mbps
from app.services.path_service import segment_list


def test_parse_bw():
    assert parse_bw_mbps("bw(100Mbps)") == 100
    assert parse_bw_mbps("bw(10Gbps)") == 10000


def test_segment_list_dedup():
    d1 = Device(
        name="a", vendor=Vendor.JUNIPER, overlay_tech=OverlayTech.SRMPLS_EVPN,
        mgmt_ip="1.1.1.1", sr_node_sid=100,
    )
    d2 = Device(
        name="b", vendor=Vendor.JUNIPER, overlay_tech=OverlayTech.SRMPLS_EVPN,
        mgmt_ip="1.1.1.2", sr_node_sid=200,
    )
    assert segment_list([d1, d2]) == [100, 200]
