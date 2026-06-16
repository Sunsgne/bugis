"""Tests for device-facing configuration labels."""
from __future__ import annotations

from app.models.circuit import Circuit
from app.models.tenant import Tenant
from app.services import labeling


def test_format_vsi_description_uses_tenant_code_not_db_id():
    tenant = Tenant(name="天网恢恢", code="TIANWANG")
    circuit = Circuit(
        name="test",
        code="CIR-5E807D",
        tenant_id=4,
        description=None,
    )
    assert labeling.format_vsi_description(circuit, tenant) == "TIANWANG · test [CIR-5E807D]"


def test_format_vsi_description_prefers_circuit_description():
    tenant = Tenant(name="天网恢恢", code="TIANWANG")
    circuit = Circuit(
        name="test",
        code="CIR-5E807D",
        tenant_id=4,
        description="跨境二层专线",
    )
    assert labeling.format_vsi_description(circuit, tenant) == "跨境二层专线"


def test_format_ac_description_default():
    tenant = Tenant(name="天网恢恢", code="TIANWANG")
    circuit = Circuit(name="test", code="CIR-5E807D", tenant_id=4)
    assert labeling.format_ac_description_default(circuit, tenant) == "TIANWANG-CIR-5E807D"
