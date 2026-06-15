"""Management defaults API."""
from __future__ import annotations


def test_management_defaults_endpoint(client, auth_headers):
    r = client.get("/api/v1/system/management-defaults", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["netconf_port"] == 830
    assert body["ssh_port"] == 22
    assert body["management_transport"] == "auto"
    assert "snmp" in body
    assert body["snmp"]["port"] == 161
