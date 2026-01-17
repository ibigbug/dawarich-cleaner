"""
Outlier detection algorithms for GPS points
- Detects unrealistic speeds
- Detects "spike / flying point" pattern (jump away then back)
- Detects stale/out-of-order timestamps
API:
    detect_outliers(points, max_speed_ms=41.67, max_distance_m=500)
"""

import math


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Great-circle distance between two points on Earth in meters.
    """
    R = 6371000.0  # Earth radius in meters
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def calculate_speed(point1, point2):
    """
    Calculate speed between two points in m/s.
    Expects point['timestamp'] to be seconds (int/float).
    """
    distance_m = haversine_distance(
        point1["latitude"],
        point1["longitude"],
        point2["latitude"],
        point2["longitude"],
    )
    dt_sec = point2["timestamp"] - point1["timestamp"]
    if dt_sec <= 0:
        return float("inf")
    return distance_m / dt_sec


def detect_outliers(points, max_speed_ms=50, max_distance_m=50):
    """
    Detect outlier GPS points.

    Args:
        points: List of dicts with keys: id, latitude, longitude, timestamp
                (timestamp as numeric value, int or float)
        max_speed_ms: Maximum realistic speed (m/s). Used for speed-based filtering.
                     Default 30 m/s = 108 km/h
        max_distance_m: Base distance threshold (meters) for spike detection and big jumps.
                       Can be as small as 5 meters for precise detection.

    Returns:
        List of outlier dicts with details (distances in meters, speeds in m/s).
    """
    if len(points) < 3:
        return []

    # Normalize input
    normalized = []
    for p in points:
        pid = int(p["id"]) if not isinstance(p["id"], int) else p["id"]
        lat = float(p["latitude"])
        lon = float(p["longitude"])
        ts = float(p["timestamp"])

        normalized.append(
            {
                "id": pid,
                "latitude": lat,
                "longitude": lon,
                "timestamp": ts,
            }
        )

    # Sort by timestamp (core requirement for sane neighbor logic)
    pts = sorted(normalized, key=lambda p: p["timestamp"])

    # Tunable derived thresholds
    # - Treat very short dt with a "big jump" as outlier even if speed calc is unstable.
    max_jump_m = max_distance_m  # Can be as small as 5m
    # Scale jump time window based on distance - smaller distances need shorter windows
    max_jump_dt_sec = max(1.0, min(10.0, max_distance_m / 50))  # 1-10s window
    # Spike rule: current far from both, but prev/next close => "jump away then back"
    spike_far_m = max_distance_m
    # For small distances, use tighter neighbor proximity
    spike_neighbor_close_m = max(max_distance_m * 2, 10)  # At least 10m

    outliers = []

    def add_outlier(cur, prev, nxt, reason, details, confidence):
        outliers.append(
            {
                "point_id": cur["id"],
                "latitude": cur["latitude"],
                "longitude": cur["longitude"],
                "timestamp": int(cur["timestamp"]),  # keep int-ish output like before
                "detection_reason": reason,
                "detection_details": details,
                "confidence_score": float(max(0.0, min(1.0, confidence))),
                "previous_point_id": prev["id"] if prev else None,
                "next_point_id": nxt["id"] if nxt else None,
            }
        )

    # Pass 1: detect stale/out-of-order within the sorted list (duplicates after sort are possible)
    # Note: after sorting, true "out-of-order" is mostly eliminated, but duplicates remain.
    for i in range(1, len(pts)):
        if pts[i]["timestamp"] <= pts[i - 1]["timestamp"]:
            # duplicate or non-increasing timestamp
            prev = pts[i - 1]
            cur = pts[i]
            nxt = pts[i + 1] if i + 1 < len(pts) else None
            add_outlier(
                cur,
                prev,
                nxt,
                reason="non_increasing_timestamp",
                details={
                    "prev_timestamp": int(prev["timestamp"]),
                    "cur_timestamp": int(cur["timestamp"]),
                },
                confidence=0.9,
            )

    # Pass 2: neighbor-based checks
    for i in range(1, len(pts) - 1):
        prev = pts[i - 1]
        cur = pts[i]
        nxt = pts[i + 1]

        dt_prev = cur["timestamp"] - prev["timestamp"]
        dt_next = nxt["timestamp"] - cur["timestamp"]
        dt_prevnext = nxt["timestamp"] - prev["timestamp"]

        d_prev_cur = haversine_distance(
            prev["latitude"], prev["longitude"], cur["latitude"], cur["longitude"]
        )
        d_cur_next = haversine_distance(
            cur["latitude"], cur["longitude"], nxt["latitude"], nxt["longitude"]
        )
        d_prev_next = haversine_distance(
            prev["latitude"], prev["longitude"], nxt["latitude"], nxt["longitude"]
        )

        # Speeds (m/s)
        speed_to = calculate_speed(prev, cur) if dt_prev > 0 else float("inf")
        speed_from = calculate_speed(cur, nxt) if dt_next > 0 else float("inf")
        speed_direct = calculate_speed(prev, nxt) if dt_prevnext > 0 else float("inf")

        # A) Speed outlier: impossible speed either entering or leaving the point
        # Use a small tolerance so borderline values don't flap.
        speed_tol = 1.15
        speed_flag = (speed_to > max_speed_ms * speed_tol) or (
            speed_from > max_speed_ms * speed_tol
        )

        # B) Short-window big jump: very large distance in a very small dt
        jump_flag = (dt_prev > 0 and dt_prev < max_jump_dt_sec and d_prev_cur > max_jump_m) or (
            dt_next > 0 and dt_next < max_jump_dt_sec and d_cur_next > max_jump_m
        )

        # C) Spike (flying point): far from both neighbors, but neighbors are close to each other
        spike_flag = (
            d_prev_cur > spike_far_m
            and d_cur_next > spike_far_m
            and d_prev_next < spike_neighbor_close_m
        )

        if not (speed_flag or jump_flag or spike_flag):
            continue

        # Build confidence (0..1)
        # Distance severity (how far away)
        avg_far_m = (d_prev_cur + d_cur_next) / 2.0
        distance_factor = min(1.0, avg_far_m / max(spike_far_m * 2.0, 0.001))

        # Detour severity (how much longer via cur vs direct)
        detour_m = (d_prev_cur + d_cur_next) - d_prev_next
        detour_ratio = detour_m / max(d_prev_next, 50.0)  # 50m baseline
        detour_factor = min(1.0, detour_ratio / 5.0)  # 5x detour -> 1.0

        # Speed severity
        max_req_speed = max(speed_to, speed_from)
        speed_factor = 0.0
        if math.isfinite(max_req_speed):
            # 0 at <= max_speed_ms, 1 at >= 2*max_speed_ms
            speed_factor = min(
                1.0, max(0.0, (max_req_speed - max_speed_ms) / max(max_speed_ms, 1.0))
            )

        # Weighted confidence: spike pattern is usually very strong signal
        confidence = 0.25 * distance_factor + 0.35 * detour_factor + 0.40 * speed_factor
        if spike_flag:
            confidence = max(confidence, 0.85)  # spike is very diagnostic
        if jump_flag and max_req_speed > max_speed_ms * 2:
            confidence = max(confidence, 0.9)

        # Pick a reason string (single label) but include all signals in details
        if spike_flag:
            reason = "flying_point"
        elif speed_flag:
            reason = "speed_outlier"
        else:
            reason = "jump_outlier"

        details = {
            "distance_from_prev_m": round(d_prev_cur, 1),
            "distance_to_next_m": round(d_cur_next, 1),
            "direct_route_m": round(d_prev_next, 1),
            "time_to_point_sec": int(dt_prev) if dt_prev > 0 else int(dt_prev),
            "time_from_point_sec": int(dt_next) if dt_next > 0 else int(dt_next),
            "speed_to_point_ms": (round(speed_to, 1) if math.isfinite(speed_to) else None),
            "speed_from_point_ms": (round(speed_from, 1) if math.isfinite(speed_from) else None),
            "speed_direct_ms": (round(speed_direct, 1) if math.isfinite(speed_direct) else None),
            "thresholds": {
                "max_speed_ms": max_speed_ms,
                "max_distance_m": max_distance_m,
                "max_jump_dt_sec": max_jump_dt_sec,
            },
            "signals": {
                "speed_flag": bool(speed_flag),
                "jump_flag": bool(jump_flag),
                "spike_flag": bool(spike_flag),
            },
            "confidence_breakdown": {
                "distance_factor": round(distance_factor, 2),
                "detour_factor": round(detour_factor, 2),
                "speed_factor": round(speed_factor, 2),
            },
        }

        add_outlier(cur, prev, nxt, reason, details, confidence)

    return outliers
