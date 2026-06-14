"""Bugis built-in SDN controller (self-developed, no external dependency).

Maintains an EVPN control plane (VTEP registry + RIB) and computes the routes
that would be reflected across the fabric, acting as the fabric brain.
"""
from app.controller.engine import BugisController, controller

__all__ = ["BugisController", "controller"]
