"""Southbound vendor drivers.

Each driver renders vendor-specific configuration from a normalized intent
and (optionally) pushes it to a device. The platform runs in dry-run mode by
default so it works end-to-end without lab hardware.
"""
from app.drivers.base import BaseDriver, DriverResult
from app.drivers.registry import get_driver, list_drivers

__all__ = ["BaseDriver", "DriverResult", "get_driver", "list_drivers"]
