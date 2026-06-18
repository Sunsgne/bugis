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
# ``return`` jumps all the way out to user view; netmiko's exit_config_mode
# handles leaving config mode for us, and sending it mid-paste would break
# prompt detection, so it is always dropped.
#
# ``quit`` only pops ONE view level (e.g. interface-view -> system-view). It is
# required mid-config when a teardown removes interface-scoped config and then
# has to issue system-view ``undo`` commands (undo vsi / undo qos policy /
# undo bridge-domain). Without it the CLI stays in interface view and those
# commands silently fail, leaving dirty config behind, so ``quit`` is kept.
_HASH_VENDOR_EXIT = re.compile(r"^\s*return\s*$", re.IGNORECASE)

# ``commit`` (VRP8 two-stage) and ``save`` / ``save force`` (persist to startup)
# are rendered into the displayed config for operator visibility, but the live
# push performs them through the transport layer (netmiko ``commit`` /
# ``save_config`` with interactive ``Y`` handling, or the H3C NETCONF save RPC),
# never as plain batched config commands — sending a bare ``save`` mid-batch
# stalls on its "Are you sure? [Y/N]" prompt. So strip them from the command
# list; the transport layer owns commit/save.
_HASH_PERSIST = re.compile(r"^\s*(commit|save(\s+force)?)\s*$", re.IGNORECASE)

# Cisco / Arista / FRR comment marker.
_BANG_COMMENT = re.compile(r"^\s*!")
# Junos annotation lines (## ... or # ...) emitted by templates.
_JUNOS_COMMENT = re.compile(r"^\s*#{1,2}(\s|$)")


def _clean_hash_vendor(config: str) -> list[str]:
    """H3C / Huawei: drop banners, bare ``#`` separators and ``return``.

    ``quit`` is intentionally preserved so teardown templates can pop back to
    system-view before issuing system-scoped ``undo`` commands.
    """
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
        if _HASH_PERSIST.match(line):
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
