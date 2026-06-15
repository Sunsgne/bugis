"""Bundled MIB registry tests."""
from __future__ import annotations

from app.services.mib_registry import IF_MIB, IF_OPER_STATUS, list_bundled_mibs


def test_if_mib_oids_match_rfc2863():
    assert IF_MIB.ifDescr.oid == "1.3.6.1.2.1.2.2.1.2"
    assert IF_MIB.ifName.oid == "1.3.6.1.2.1.31.1.1.1.1"
    assert IF_MIB.ifAlias.oid == "1.3.6.1.2.1.31.1.1.1.18"
    assert IF_MIB.ifHighSpeed.oid == "1.3.6.1.2.1.31.1.1.1.15"
    assert IF_MIB.ifOperStatus.oid == "1.3.6.1.2.1.2.2.1.8"
    assert IF_MIB.ifHCInOctets.oid == "1.3.6.1.2.1.31.1.1.1.6"
    assert IF_MIB.ifHCOutOctets.oid == "1.3.6.1.2.1.31.1.1.1.10"
    assert IF_MIB.ifHCInOctets.column(5) == "1.3.6.1.2.1.31.1.1.1.6.5"


def test_if_oper_status_map():
    assert IF_OPER_STATUS[1] == "up"
    assert IF_OPER_STATUS[2] == "down"


def test_bundled_mib_manifest():
    mibs = list_bundled_mibs()
    assert any(m["mib"] == "IF-MIB" for m in mibs)
    if_mib = next(m for m in mibs if m["mib"] == "IF-MIB")
    assert if_mib["rfc"] == "RFC2863"


def test_snmp_mibs_api(client, auth_headers):
    r = client.get("/api/v1/system/snmp/mibs", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert any(o["symbol"] == "ifName" for o in body["oids_in_use"])
    assert any(m["mib"] == "IF-MIB" for m in body["manifest"])
