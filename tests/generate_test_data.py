#!/usr/bin/env python3
"""Generate synthetic GPS test data with known outliers."""

import math
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path to import detector
sys.path.insert(0, str(Path(__file__).parent))

from app.services.outlier_detector import detect_outliers

# Start at a generic ocean location
BASE_LAT = 0.0  # Equator
BASE_LON = 60.0  # Indian Ocean
BASE_TIME = datetime(2024, 6, 15, 10, 0, 0)  # Generic date


def create_normal_path(num_points=100):
    """Create a normal walking path."""
    points = []
    lat, lon = BASE_LAT, BASE_LON
    timestamp = BASE_TIME

    for i in range(num_points):
        # Simulate walking: ~1.4 m/s, 5 seconds between points
        # Distance per step: ~7 meters
        dlat = 0.00006 * (1 + 0.2 * math.sin(i / 10))  # ~7m north, slight variation
        dlon = 0.00005 * (1 + 0.2 * math.cos(i / 10))  # ~6m east, slight variation

        lat += dlat
        lon += dlon
        timestamp += timedelta(seconds=5)

        points.append(
            {
                "lat": lat,
                "lon": lon,
                "time": timestamp,
                "ele": 10.0 + 2 * math.sin(i / 20),  # Slight elevation change
                "type": "normal",
            }
        )

    return points


def inject_speed_outlier(points, index):
    """Inject a point that requires impossible speed without creating jump pattern."""
    if index >= len(points) or index == 0 or index >= len(points) - 1:
        return

    # Create a gradual acceleration/deceleration pattern
    # Only shift this single point slightly - enough to create speed violation
    # but not enough to create a large distance jump
    # 150m shift with 5 sec intervals = 30 m/s speed (just over 50 m/s threshold when combined)
    points[index]["lat"] += 0.00135  # ~150m
    points[index]["lon"] += 0.00135  # ~150m

    points[index]["type"] = "speed_outlier"


def inject_jump_with_return(points, index):
    """Inject a jump outlier (jumps away and back creating spike pattern)."""
    if index >= len(points) or index == 0:
        return

    # Jump 600m away from the path (spike pattern)
    points[index]["lat"] += 0.0054
    points[index]["lon"] -= 0.0054
    points[index]["type"] = "jump_outlier"


def inject_duplicate_timestamp(points, index):
    """Create duplicate timestamp."""
    if index >= len(points) or index == 0:
        return

    points[index]["time"] = points[index - 1]["time"]
    points[index]["type"] = "duplicate_timestamp"


def inject_jump_outlier(points, index):
    """Inject a point with large distance jump."""
    if index >= len(points):
        return

    # Jump 80m away (exceeds 50m threshold but not extreme)
    points[index]["lat"] += 0.0007
    points[index]["lon"] += 0.0007
    points[index]["type"] = "jump_outlier"


# Generate base path
print("📍 Generating synthetic GPS data...")
points = create_normal_path(200)

# Inject various outliers
print("🚩 Injecting outliers...")
inject_speed_outlier(points, 30)
inject_jump_with_return(points, 50)
inject_jump_with_return(points, 51)  # Next point returns (spike pattern)
inject_speed_outlier(points, 75)
inject_jump_outlier(points, 100)
inject_duplicate_timestamp(points, 120)
inject_jump_with_return(points, 150)
inject_jump_outlier(points, 175)

outlier_count = sum(1 for p in points if p["type"] != "normal")
print(f"   Total points: {len(points)}")
print(f"   Normal points: {len(points) - outlier_count}")
print(f"   Outliers: {outlier_count}")

# Create GPX
gpx_ns = "http://www.topografix.com/GPX/1/1"
ET.register_namespace("", gpx_ns)

root = ET.Element(
    "{" + gpx_ns + "}gpx",
    {"version": "1.1", "creator": "Synthetic Test Data Generator"},
)

metadata = ET.SubElement(root, "metadata")
name = ET.SubElement(metadata, "name")
name.text = "Synthetic GPS Test Data"
time_elem = ET.SubElement(metadata, "time")
time_elem.text = datetime.now().isoformat() + "Z"

trk = ET.SubElement(root, "trk")
trk_name = ET.SubElement(trk, "name")
trk_name.text = "Test Track with Known Outliers"
trkseg = ET.SubElement(trk, "trkseg")

for point in points:
    trkpt = ET.SubElement(
        trkseg, "trkpt", {"lat": f"{point['lat']:.7f}", "lon": f"{point['lon']:.7f}"}
    )

    time_elem = ET.SubElement(trkpt, "time")
    time_elem.text = point["time"].isoformat() + "Z"

    ele = ET.SubElement(trkpt, "ele")
    ele.text = f"{point['ele']:.1f}"

# Save
output_file = "tests/test_sample.gpx"
tree = ET.ElementTree(root)
ET.indent(tree, space="  ")
tree.write(output_file, encoding="utf-8", xml_declaration=True)

print(f"\n✅ Synthetic test GPX saved to: {output_file}")

# Now detect actual outliers to report accurate counts
# Convert to format expected by detector
detector_points = [
    {
        "latitude": p["lat"],
        "longitude": p["lon"],
        "timestamp": p["time"].timestamp(),
        "altitude": p["ele"],
        "id": i + 1,
    }
    for i, p in enumerate(points)
]

# Detect with default thresholds
detected_outliers = detect_outliers(detector_points, max_speed_ms=50, max_distance_m=50)
detected_lenient = detect_outliers(detector_points, max_speed_ms=100, max_distance_m=1000)

print("\n📊 Injected outlier types:")
for outlier_type in [
    "speed_outlier",
    "jump_outlier",
    "duplicate_timestamp",
]:
    count = sum(1 for p in points if p["type"] == outlier_type)
    if count > 0:
        print(f"   - {outlier_type}: {count}")

print("\n🔍 Actually detected outliers (with 50 m/s, 50m thresholds):")
print(f"   Total: {len(detected_outliers)}")
reason_counts = {}
for o in detected_outliers:
    reason = o["detection_reason"]
    reason_counts[reason] = reason_counts.get(reason, 0) + 1
for reason, count in sorted(reason_counts.items()):
    print(f"   - {reason}: {count}")

print("\n🔍 Detected with lenient thresholds (100 m/s, 1000m):")
print(f"   Total: {len(detected_lenient)}")
reason_counts_lenient = {}
for o in detected_lenient:
    reason = o["detection_reason"]
    reason_counts_lenient[reason] = reason_counts_lenient.get(reason, 0) + 1
for reason, count in sorted(reason_counts_lenient.items()):
    print(f"   - {reason}: {count}")
