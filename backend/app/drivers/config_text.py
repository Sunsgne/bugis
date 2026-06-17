"""Vendor-aware helpers to turn rendered "display-style" config into a clean,
paste-safe command list for CLI (netmiko) / NETCONF CLI-RPC delivery.

Why this exists
---------------
The Jinja2 templates intentionally render configuration the way a device prints
its own ``display current-configuration`` / ``show configuration`` output:

  * H3C (Comware7) / Huawei (VRP): banner ``# ...`` comment lines, bare ``#``
    section separators, and a trailing ``return``.
  * FRRouting: ``! ...`` comment lines, wrapped in ``configure terminal`` / ``end``.
  * Juniper (Junos): ``##`` / ``#`` annotation lines, ``set ...`` statements.
  * Cisco IOS-XR / Arista EOS: ``! ...`` comment lines.

That format is great for humans and for the dry-run preview, but it is NOT safe
to paste into a live CLI session:

  * The trailing ``return`` (Comware/VRP) exits ``system-view`` back to user
    view, so netmiko's post-config prompt detection times out
    ("Pattern not detected") — the exact failure reported in production when
    pushing to a Huawei device with a very long hostname.
  * Banner ``# device=...`` comment lines are echoed and confuse prompt
    matching / may raise errors on some VRP releases.

``to_command_list`` strips the non-command noise per vendor and returns a list
of commands suitable for ``netmiko.send_config_set`` (which enters/exits config
mode on its own) or for wrapping inside a vendor NETCONF CLI RPC.
"""
from __future__ import annotations

import re

from app.models.enums import Vendor

# H3C / Huawei: a line that is just "#" (optionally with surrounding spaces) is a
# section separator in display output; a line like "# text" is a banner comment.
_HASH_SEPARATOR = re.compile(r"^\s*#\s*$")
_HASH_COMMENT = re.compile(r"^\s*#\s+\S")
# Top-level navigation that netmiko's exit_config_mode handles for us; sending it
# mid-paste exits system-view and breaks prompt detection.
_HASH_VENDOR_EXIT = re.compile(r"^\s*(return|quit)\s*$", re.IGNORECASE)

# Cisco / Arista / FRR comment marker.
_BANG_COMMENT = re.compile(r"^\s*!")
# Junos annotation lines (## ... or # ...) emitted by templates.
_JUNOS_COMMENT = re.compile(r"^\s*#{1,2}(\s|$)")


def _clean_hash_vendor(config: str) -> list[str]:
    """H3C / Huawei: drop banners, bare ``#`` separators and trailing return/quit."""
    commands: list[str] = []
    for raw in config.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if _HASH_SEPARATOR.match(line):
            continue
        if _HASH_COMMENT.match(line):
            continue
        if _HASH_VENDOR_EXIT.match(line):
            continue
        commands.append(line)
    return commands


def _clean_bang_vendor(config: str) -> list[str]:
    """Cisco / Arista / FRR: drop ``!`` comment lines and blank lines."""
    commands: list[str] = []
    for raw in config.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if _BANG_COMMENT.match(line):
            continue
        commands.append(line)
    return commands


def _clean_junos(config: str) -> list[str]:
    """Juniper: drop ``#`` / ``##`` annotation lines and blank lines."""
    commands: list[str] = []
    for raw in config.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if _JUNOS_COMMENT.match(line):
            continue
        commands.append(line)
    return commands


def to_command_list(vendor: Vendor, config: str) -> list[str]:
    """Return a paste-safe command list for the given vendor.

    The result never contains comment/banner lines, blank lines, or top-level
    ``return`` / ``quit`` that would prematurely leave config mode.
    """
    if config is None:
        return []
    if vendor in (Vendor.H3C, Vendor.HUAWEI):
        return _clean_hash_vendor(config)
    if vendor == Vendor.JUNIPER:
        return _clean_junos(config)
    # Cisco / Arista / FRR (and any future vendor) use ``!`` comments.
    return _clean_bang_vendor(config)


def to_command_text(vendor: Vendor, config: str) -> str:
    """Newline-joined paste-safe commands (handy for NETCONF CLI RPC payloads)."""
    return "\n".join(to_command_list(vendor, config))
