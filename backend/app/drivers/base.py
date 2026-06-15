"""Base southbound driver.

A driver is responsible for:
  1. Rendering vendor configuration from a normalized intent (Jinja2 templates).
  2. Optionally pushing that configuration to a device (NETCONF / CLI).

Real device transport (netmiko / ncclient) is imported lazily; packages are
listed in requirements.txt for production (dry_run=false) deployments.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.enums import OverlayTech, Vendor

TEMPLATE_ROOT = os.path.join(os.path.dirname(__file__), "..", "templates")


@dataclass
class DriverResult:
    """Outcome of a render or push operation."""

    success: bool
    config: str = ""
    rollback: str = ""
    output: str = ""
    dry_run: bool = True
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None


class BaseDriver:
    """Base class for vendor drivers."""

    vendor: Vendor
    overlay_tech: OverlayTech
    #: relative folder under app/templates that holds this vendor's templates
    template_dir: str
    #: default transport used for this vendor
    transport: str = "netconf"

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(os.path.abspath(TEMPLATE_ROOT)),
            autoescape=select_autoescape(enabled_extensions=()),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    # --- rendering -----------------------------------------------------
    def _template_name(self, service_type: str, operation: str) -> str:
        return f"{self.template_dir}/{service_type}_{operation}.j2"

    def render(
        self, service_type: str, operation: str, context: dict[str, Any]
    ) -> str:
        """Render configuration for a given service type and operation.

        Falls back to a generic template if a vendor-specific one is missing.
        """
        ctx = dict(context)
        ctx.setdefault("vendor", self.vendor.value)
        ctx.setdefault("overlay_tech", self.overlay_tech.value)
        ctx.setdefault("operation", operation)

        name = self._template_name(service_type, operation)
        try:
            template = self._env.get_template(name)
        except Exception:
            # Fallback: generic template that documents the intent.
            template = self._env.get_template(f"_generic/{service_type}_{operation}.j2")
        return template.render(**ctx)

    # --- pushing -------------------------------------------------------
    def push(
        self,
        device: Any,
        config: str,
        dry_run: bool = True,
    ) -> DriverResult:
        """Push configuration to a device.

        In dry-run mode (default) we only simulate the push and return the
        config as the captured output. When dry_run is False we attempt a real
        NETCONF/SSH push, importing transport libraries lazily.
        """
        result = DriverResult(success=True, config=config, dry_run=dry_run)
        if dry_run:
            result.output = self._simulate_push(device, config)
            result.finished_at = datetime.now(timezone.utc)
            return result

        try:
            result.output = self._real_push(device, config)
            result.success = True
        except Exception as exc:  # pragma: no cover - depends on live device
            result.success = False
            result.output = f"PUSH FAILED: {exc}"
        result.finished_at = datetime.now(timezone.utc)
        return result

    def _simulate_push(self, device: Any, config: str) -> str:
        lines = config.strip().splitlines()
        header = (
            f"[DRY-RUN] vendor={self.vendor.value} "
            f"device={getattr(device, 'name', 'unknown')} "
            f"({getattr(device, 'mgmt_ip', '-')}) transport={self.transport}\n"
            f"[DRY-RUN] {len(lines)} config line(s) would be applied:\n"
        )
        return header + config

    def fetch_config(self, device: Any, dry_run: bool = True) -> DriverResult:
        """Pull running-config from device (NETCONF get-config or CLI show run)."""
        result = DriverResult(success=True, dry_run=dry_run)
        if dry_run:
            from app.services.config_fetch import simulated_config

            result.config = simulated_config(device)
            result.output = (
                f"[DRY-RUN] fetched {len(result.config.splitlines())} line(s) "
                f"from {getattr(device, 'name', 'unknown')}"
            )
            result.finished_at = datetime.now(timezone.utc)
            return result
        try:
            result.config = self._real_fetch(device)
            result.output = f"fetched {len(result.config.splitlines())} line(s)"
            result.success = True
        except Exception as exc:  # pragma: no cover
            result.success = False
            result.output = f"FETCH FAILED: {exc}"
        result.finished_at = datetime.now(timezone.utc)
        return result

    def _real_fetch(self, device: Any) -> str:  # pragma: no cover
        from app.services.device_management import effective_transport

        if effective_transport(device) == "netconf":
            return self._fetch_netconf(device)
        return self._fetch_cli(device)

    def _fetch_netconf(self, device: Any) -> str:  # pragma: no cover
        try:
            from ncclient import manager  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "ncclient not installed; install it or run in dry-run mode"
            ) from exc
        with manager.connect(
            host=device.mgmt_ip,
            port=device.netconf_port,
            username=device.username,
            password=device.password,
            hostkey_verify=False,
            timeout=self._netconf_timeout(),
        ) as m:
            reply = m.get_config(source="running")
            return str(reply)

    def _netconf_timeout(self) -> int:
        from app.core.config import settings

        return settings.netconf_timeout

    def _cli_params(self, device: Any) -> dict:
        from app.core.config import settings
        from app.services.device_management import netmiko_device_type

        params: dict = {
            "device_type": netmiko_device_type(device),
            "host": device.mgmt_ip,
            "port": device.ssh_port,
            "username": device.username,
            "password": device.password,
            "conn_timeout": getattr(settings, "ssh_timeout", 30),
        }
        if getattr(device, "enable_password", None):
            params["secret"] = device.enable_password
        return params

    def _fetch_cli(self, device: Any) -> str:  # pragma: no cover
        try:
            from netmiko import ConnectHandler  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "netmiko not installed; install it or run in dry-run mode"
            ) from exc
        conn = ConnectHandler(**self._cli_params(device))
        try:
            if self.vendor == Vendor.JUNIPER:
                return conn.send_command("show configuration | display set")
            if self.vendor in (Vendor.H3C, Vendor.HUAWEI):
                return conn.send_command("display current-configuration")
            return conn.send_command("show running-config")
        finally:
            conn.disconnect()

    def _real_push(self, device: Any, config: str) -> str:  # pragma: no cover
        """Real push hook. Subclasses may override per transport.

        Default tries NETCONF via ncclient, falling back to CLI via netmiko.
        """
        from app.services.device_management import effective_transport

        if effective_transport(device) == "netconf":
            return self._push_netconf(device, config)
        return self._push_cli(device, config)

    def _push_netconf(self, device: Any, config: str) -> str:  # pragma: no cover
        try:
            from ncclient import manager  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "ncclient not installed; install it or run in dry-run mode"
            ) from exc
        with manager.connect(
            host=device.mgmt_ip,
            port=device.netconf_port,
            username=device.username,
            password=device.password,
            hostkey_verify=False,
            timeout=self._netconf_timeout(),
        ) as m:
            reply = m.edit_config(target="running", config=config)
            return str(reply)

    def _push_cli(self, device: Any, config: str) -> str:  # pragma: no cover
        try:
            from netmiko import ConnectHandler  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "netmiko not installed; install it or run in dry-run mode"
            ) from exc
        conn = ConnectHandler(**self._cli_params(device))
        try:
            return conn.send_config_set(config.splitlines())
        finally:
            conn.disconnect()


NETMIKO_DEVICE_TYPES = {
    Vendor.H3C: "hp_comware",
    Vendor.HUAWEI: "huawei",
    Vendor.JUNIPER: "juniper_junos",
    Vendor.ARISTA: "arista_eos",
    Vendor.CISCO: "cisco_xr",
}
