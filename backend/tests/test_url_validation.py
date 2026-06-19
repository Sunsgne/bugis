"""SSRF URL validation tests."""
from __future__ import annotations

import pytest

from app.core.url_validation import (
    is_internal_controller_url,
    validate_controller_base_url,
    validate_outbound_http_url,
)


def test_internal_controller_url_allowed():
    assert is_internal_controller_url("internal://bugis")
    assert validate_controller_base_url("internal://bugis") == "internal://bugis"


def test_public_https_allowed():
    url = validate_outbound_http_url("https://hooks.example.com/alarm")
    assert url == "https://hooks.example.com/alarm"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/hook",
        "http://169.254.169.254/latest/meta-data",
        "http://localhost/admin",
        "ftp://example.com/x",
        "http://user:pass@example.com/",
        "http://10.0.0.1/internal",
    ],
)
def test_blocked_urls(url: str):
    with pytest.raises(ValueError):
        validate_outbound_http_url(url)


def test_controller_rejects_internal_for_http_fields():
    with pytest.raises(ValueError):
        validate_outbound_http_url("internal://bugis")
