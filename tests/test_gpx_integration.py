"""Integration tests using real GPX sample data."""

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pytest

from app.services.outlier_detector import detect_outliers


def parse_gpx(gpx_file):
    """Parse GPX file and extract points."""
    tree = ET.parse(gpx_file)
    root = tree.getroot()
    ns = {"gpx": "http://www.topografix.com/GPX/1/1"}

    points = []
    trkpts = root.findall(".//gpx:trkpt", ns)

    for trkpt in trkpts:
        lat = float(trkpt.get("lat"))
        lon = float(trkpt.get("lon"))

        time_elem = trkpt.find("gpx:time", ns)
        if time_elem is None:
            continue

        time_str = time_elem.text
        try:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            timestamp = dt.timestamp()
        except Exception:
            continue

        ele_elem = trkpt.find("gpx:ele", ns)
        elevation = float(ele_elem.text) if ele_elem is not None else 0.0

        points.append(
            {
                "latitude": lat,
                "longitude": lon,
                "timestamp": timestamp,
                "altitude": elevation,
                "id": len(points) + 1,
            }
        )

    return points


@pytest.fixture
def gpx_sample_points():
    """Load test sample GPX file."""
    gpx_file = Path(__file__).parent / "test_sample.gpx"
    return parse_gpx(gpx_file)


def test_gpx_sample_loads(gpx_sample_points):
    """Test that the GPX sample file loads correctly."""
    assert len(gpx_sample_points) > 100
    assert all("latitude" in p for p in gpx_sample_points)
    assert all("longitude" in p for p in gpx_sample_points)
    assert all("timestamp" in p for p in gpx_sample_points)


def test_gpx_sample_outlier_detection(gpx_sample_points):
    """Test outlier detection on real GPX sample data."""
    # Use default thresholds: 50 m/s (180 km/h), 50m
    outliers = detect_outliers(gpx_sample_points, max_speed_ms=50, max_distance_m=50)

    # Should detect some outliers but not all points
    assert len(outliers) > 0
    assert len(outliers) < len(gpx_sample_points)

    # All outliers should have required fields
    for outlier in outliers:
        assert "point_id" in outlier
        assert "latitude" in outlier
        assert "longitude" in outlier
        assert "timestamp" in outlier
        assert "detection_reason" in outlier
        assert "confidence_score" in outlier

        # Confidence should be between 0 and 1
        assert 0 <= outlier["confidence_score"] <= 1


def test_gpx_sample_with_strict_thresholds(gpx_sample_points):
    """Test with stricter thresholds should catch more outliers."""
    # Lenient thresholds
    outliers_lenient = detect_outliers(gpx_sample_points, max_speed_ms=100, max_distance_m=1000)

    # Strict thresholds
    outliers_strict = detect_outliers(gpx_sample_points, max_speed_ms=10, max_distance_m=20)

    # Stricter thresholds should catch more outliers
    assert len(outliers_strict) >= len(outliers_lenient)


def test_gpx_sample_outlier_reasons(gpx_sample_points):
    """Test that outliers have valid detection reasons."""
    outliers = detect_outliers(gpx_sample_points, max_speed_ms=50, max_distance_m=50)

    valid_reasons = {
        "speed_outlier",
        "flying_point",
        "jump_outlier",
        "non_increasing_timestamp",
    }

    for outlier in outliers:
        assert outlier["detection_reason"] in valid_reasons


def test_gpx_cleaned_data_quality(gpx_sample_points):
    """Test that removing outliers maintains data quality."""
    outliers = detect_outliers(gpx_sample_points, max_speed_ms=50, max_distance_m=50)
    outlier_ids = {o["point_id"] for o in outliers}

    cleaned_points = [p for p in gpx_sample_points if p["id"] not in outlier_ids]

    # Should retain most points
    retention_rate = len(cleaned_points) / len(gpx_sample_points)
    assert retention_rate > 0.9  # At least 90% retention

    # Cleaned data should still be sequential
    timestamps = [p["timestamp"] for p in cleaned_points]
    assert timestamps == sorted(timestamps)
