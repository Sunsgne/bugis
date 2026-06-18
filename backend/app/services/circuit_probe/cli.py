"""Run read-only CLI commands on devices via SSH."""
from __future__ import annotations

from app.drivers.registry import get_driver
from app.models.device import Device
from app.models.enums import Vendor
from app.services.device_management import ssh_timeout


def run_cli(device: Device, command: str, *, read_timeout: int | None = None) -> str:
    """Execute one show/ping command on a device (production only)."""
    try:
        from netmiko import ConnectHandler  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("netmiko not installed") from exc

    driver = get_driver(device.vendor)
    params = driver._cli_params(device)  # noqa: SLF001 — shared with drivers
    timeout = read_timeout or driver._cli_read_timeout()  # noqa: SLF001
    conn = ConnectHandler(**params)
    try:
        driver._prepare_cli_session(conn)  # noqa: SLF001
        return conn.send_command(command, read_timeout=timeout)
    finally:
        conn.disconnect()


def ping_command(device: Device, target_ip: str, *, count: int = 5, interval_ms: int = 200) -> str:
    if device.vendor == Vendor.H3C:
        return f"ping -c {count} -m {interval_ms} {target_ip}"
    if device.vendor == Vendor.HUAWEI:
        return f"ping -c {count} -m {interval_ms} {target_ip}"
    return f"ping -c {count} {target_ip}"


def h3c_mac_lookup_command(vsi_name: str) -> str:
    return f"display l2vpn mac-address vsi {vsi_name}"


def h3c_vsi_mac_ping_command(vsi_name: str, mac: str, *, count: int = 5) -> str:
    return f"ping vsi {vsi_name} mac {mac} -c {count}"


def h3c_vni_ping_command(vni: int, target_ip: str, *, count: int = 5) -> str:
    return f"ping -a vxlan vni {vni} ip {target_ip} -c {count}"


def huawei_vni_ping_command(vni: int, target_ip: str, *, count: int = 5) -> str:
    return f"ping vxlan vni {vni} peer-ip {target_ip} -c {count}"


def can_run_live(device: Device) -> bool:
    from app.services.credential_store import decrypt_value

    return bool(
        device.active_mgmt_ip
        and device.username
        and decrypt_value(device.password)
    )
