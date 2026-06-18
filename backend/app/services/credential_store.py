"""Encrypt / decrypt southbound credentials at rest (Fernet via secret_key)."""
from __future__ import annotations

from typing import Any

from app.services import auth_security

_PREFIX = "enc$"

_SENSITIVE_DEVICE_FIELDS = (
    "password",
    "enable_password",
    "snmp_community",
    "snmp_v3_auth_password",
    "snmp_v3_priv_password",
)


def is_encrypted(value: str | None) -> bool:
    return bool(value and value.startswith(_PREFIX))


def encrypt_value(value: str | None) -> str | None:
    if not value:
        return None
    if is_encrypted(value):
        return value
    return _PREFIX + auth_security.encrypt_secret(value)


def decrypt_value(value: str | None) -> str | None:
    if not value:
        return None
    if is_encrypted(value):
        return auth_security.decrypt_secret(value[len(_PREFIX) :])
    return value


def encrypt_device_fields(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    for key in _SENSITIVE_DEVICE_FIELDS:
        if key in out and out[key] is not None:
            out[key] = encrypt_value(out[key])
    return out


def encrypt_device_model(device: Any) -> None:
    for key in _SENSITIVE_DEVICE_FIELDS:
        val = getattr(device, key, None)
        if val:
            setattr(device, key, encrypt_value(val))


def decrypt_device_secret(device: Any, field: str) -> str | None:
    return decrypt_value(getattr(device, field, None))


def southbound_device(device: Any) -> Any:
    """Shallow copy of *device* with decrypted SSH / enable passwords for drivers."""
    if device is None:
        return device
    clone = type("SouthboundDevice", (), {})()
    for attr in (
        "vendor", "name", "username", "management_transport", "active_mgmt_ip",
        "mgmt_ip", "ssh_port", "netconf_port", "netmiko_device_type", "password",
        "enable_password",
    ):
        if hasattr(device, attr):
            setattr(clone, attr, getattr(device, attr))
    clone.password = decrypt_value(getattr(device, "password", None))
    clone.enable_password = decrypt_value(getattr(device, "enable_password", None))
    return clone
