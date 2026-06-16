"""Human-readable labels for rendered device configuration."""
from __future__ import annotations

from app.models.circuit import Circuit
from app.models.tenant import Tenant


def tenant_label(tenant: Tenant | None, tenant_id: int) -> str:
    if tenant is None:
        return f"T{tenant_id}"
    return tenant.code or tenant.name


def format_vsi_description(
    circuit: Circuit,
    tenant: Tenant | None = None,
) -> str:
    """VSI / EVPN service description shown on devices."""
    if circuit.description and circuit.description.strip():
        return circuit.description.strip()[:255]
    label = tenant_label(tenant, circuit.tenant_id)
    return f"{label} · {circuit.name} [{circuit.code}]"[:255]


def format_ac_description_default(
    circuit: Circuit,
    tenant: Tenant | None = None,
) -> str:
    """Default AC / service-instance description when endpoint text is empty."""
    label = tenant_label(tenant, circuit.tenant_id)
    return f"{label}-{circuit.code}"[:255]
