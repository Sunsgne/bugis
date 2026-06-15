"""Enum storage compatibility tests."""
from __future__ import annotations

from app.models.enums import AccessMode, PathMode
from app.models.mixins import str_enum_column


def test_str_enum_column_uses_values():
    path_col = str_enum_column(PathMode)
    access_col = str_enum_column(AccessMode)
    assert "auto" in path_col.enums
    assert "explicit_sr" in path_col.enums
    assert "dot1q" in access_col.enums
    assert "AUTO" not in path_col.enums


def test_path_mode_enum_values():
    assert PathMode("auto") == PathMode.AUTO
    assert AccessMode("dot1q") == AccessMode.DOT1Q
