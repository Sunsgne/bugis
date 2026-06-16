"""Northbound integration endpoints: webhook intake & Ansible export."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_platform_user
from app.core.config import settings
from app.core.database import get_db
from app.drivers import list_drivers
from app.models.circuit import Circuit, CircuitEndpoint
from app.models.device import Device
from app.models.enums import WorkOrderType
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.integration import WebhookProvision
from app.schemas.workorder import WorkOrderOut
from app.services import allocation, ansible_export, orchestrator

router = APIRouter()


def _verify_webhook(x_webhook_token: str | None) -> None:
    if x_webhook_token != settings.webhook_token:
        raise HTTPException(status_code=401, detail="invalid webhook token")


@router.post("/webhook/provision", response_model=WorkOrderOut, status_code=201)
def webhook_provision(
    payload: WebhookProvision,
    db: Session = Depends(get_db),
    x_webhook_token: str | None = Header(default=None),
):
    """Event-driven intake (StackStorm/ITSM): create + provision a circuit.

    Authenticated via the shared `X-Webhook-Token` header rather than a user
    session, so external orchestrators can drive provisioning automatically.
    """
    _verify_webhook(x_webhook_token)

    tenant = db.execute(
        select(Tenant).where(Tenant.code == payload.tenant_code)
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant not found")

    circuit = Circuit(
        name=payload.name,
        code=allocation.next_circuit_code(db),
        tenant_id=tenant.id,
        service_type=payload.service_type,
        bandwidth_mbps=payload.bandwidth_mbps,
        sla_target=payload.sla_target,
    )
    db.add(circuit)
    db.flush()

    asn = None
    endpoints: list[CircuitEndpoint] = []
    for ep in payload.endpoints:
        device = db.execute(
            select(Device).where(Device.name == ep.device_name)
        ).scalar_one_or_none()
        if not device:
            raise HTTPException(
                status_code=404, detail=f"device {ep.device_name} not found"
            )
        asn = asn or device.bgp_asn
        endpoints.append(
            CircuitEndpoint(
                circuit_id=circuit.id,
                device_id=device.id,
                label=ep.label,
                interface_name=ep.interface_name,
                vlan_id=ep.vlan_id,
                gateway_ip=ep.gateway_ip,
            )
        )
    db.add_all(endpoints)
    db.flush()
    allocation.auto_allocate_circuit_fields(db, circuit, asn)

    wo = orchestrator.create_work_order(
        db, circuit, WorkOrderType.PROVISION, requested_by="webhook"
    )
    if payload.auto_provision:
        orchestrator.submit(db, wo, actor="webhook")
        orchestrator.approve(db, wo, "webhook", approve_it=True)
        orchestrator.execute(db, wo, actor="webhook")
    db.commit()
    db.refresh(wo)
    return wo


@router.get("/ansible/inventory")
def ansible_inventory(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_user),
):
    text = ansible_export.export_inventory(db)
    return Response(content=text, media_type="text/plain")


@router.get("/catalog")
def integration_catalog(_: User = Depends(require_platform_user)):
    return {
        "drivers": list_drivers(),
        "webhook": {
            "url": f"{settings.api_v1_prefix}/integrations/webhook/provision",
            "header": "X-Webhook-Token",
        },
        "ansible": {
            "inventory_url": f"{settings.api_v1_prefix}/integrations/ansible/inventory",
            "playbook_per_work_order": (
                f"{settings.api_v1_prefix}/work-orders/{{id}}/ansible"
            ),
        },
    }
