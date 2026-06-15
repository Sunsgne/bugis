"""Tests for bw(...) port description parsing."""
from app.services.bw_parser import format_bw_tag, parse_bw_mbps


def test_parse_bw_mbps_variants():
    assert parse_bw_mbps("backbone DCI bw(100Mbps)") == 100
    assert parse_bw_mbps("uplink bw(10Gbps)") == 10000
    assert parse_bw_mbps("bw(100M)") == 100
    assert parse_bw_mbps("BW(2.5Gbps)") == 2500
    assert parse_bw_mbps("no tag here") is None
    assert parse_bw_mbps(None) is None


def test_format_bw_tag():
    assert format_bw_tag(100) == "bw(100Mbps)"
    assert format_bw_tag(10000) == "bw(10Gbps)"
