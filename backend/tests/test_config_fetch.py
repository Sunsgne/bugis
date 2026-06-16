"""Tests for running-config fetch validation."""
from __future__ import annotations

from app.models.enums import Vendor
from app.services.config_fetch import looks_like_running_config

H3C_CONFIG = """\
sysname BJ-LEAF-01
#
interface LoopBack0
 ip address 10.1.255.11 255.255.255.255
#
bgp 65001
 router-id 10.1.255.11
#
interface GE1/0/5
 port link-mode bridge
 service-instance 120
  encapsulation s-vid 120
#
return
"""


def test_looks_like_running_config_accepts_real_h3c():
    assert looks_like_running_config(H3C_CONFIG, Vendor.H3C) is True


def test_looks_like_running_config_rejects_prompt_echo():
    prompt_only = "\n".join(
        [
            "<cs-6.megahkg4-32f-g0112-u8.iptpe>",
            "<cs-6.megahkg4-32f-g0112-u8.iptpe>",
            "<cs-6.megahkg4-32f-g0112-u8.iptpe>",
            "<cs-6.megahkg4-32f-g0112-u8.iptpe>",
        ]
    )
    assert looks_like_running_config(prompt_only, Vendor.H3C) is False


def test_looks_like_running_config_rejects_short_output():
    assert looks_like_running_config("sysname TEST\nreturn\n", Vendor.H3C) is False
