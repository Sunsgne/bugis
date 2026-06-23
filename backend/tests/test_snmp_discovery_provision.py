"""Tests for post-provision SNMP discovery hook."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.models.enums import WorkOrderType
from app.services import orchestrator


def test_schedule_snmp_discover_after_provision_queues_devices():
    circuit = SimpleNamespace(
        id=42,
        code="CIR-TEST",
        endpoints=[
            SimpleNamespace(device_id=1, device=SimpleNamespace(id=1)),
            SimpleNamespace(device_id=1, device=SimpleNamespace(id=1)),
            SimpleNamespace(device_id=2, device=SimpleNamespace(id=2)),
        ],
    )
    wo = SimpleNamespace(id=9, type=WorkOrderType.PROVISION)
    logs: list[str] = []

    def _log(_db, _wo, message, **kwargs):
        logs.append(message)

    with patch(
        "app.services.snmp_discovery_service.schedule_circuit_endpoint_discovery"
    ) as schedule, patch.object(orchestrator, "_log", side_effect=_log):
        orchestrator._schedule_snmp_discover_after_provision(
            None, wo, circuit, "tester"
        )
        schedule.assert_called_once_with(42)

    assert any("SNMP 发现" in msg and "2 台" in msg for msg in logs)
