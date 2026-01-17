"""Tests for Dawarich service"""

from datetime import UTC, datetime

import pytest

from app.services.dawarich import DawarichService


@pytest.fixture
def dawarich_service():
    """Create Dawarich service instance"""
    return DawarichService("http://localhost:3000", "test_api_key")


def test_dawarich_init(dawarich_service):
    """Test Dawarich service initialization"""
    assert dawarich_service.base_url == "http://localhost:3000"
    assert dawarich_service.api_key == "test_api_key"


def test_timestamp_to_iso8601_conversion():
    """Test timestamp conversion to ISO8601"""
    # Test seconds timestamp
    ts_seconds = 1705484123
    dt = datetime.fromtimestamp(ts_seconds, tz=UTC)
    iso = dt.isoformat()
    assert "T" in iso
    assert iso.endswith("+00:00") or iso.endswith("Z")

    # Test milliseconds timestamp
    ts_millis = 1705484123000
    dt = datetime.fromtimestamp(ts_millis / 1000, tz=UTC)
    iso = dt.isoformat()
    assert "T" in iso
