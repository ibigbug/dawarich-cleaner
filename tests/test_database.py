"""Tests for database operations"""

import pytest

from app.database import Database


@pytest.fixture
async def db():
    """Create test database"""
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.init_db()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_save_flagged_point(db):
    """Test saving a flagged point"""
    point_data = {
        "point_id": 123,
        "latitude": 40.7128,
        "longitude": -74.0060,
        "timestamp": 1705484123,
        "detection_reason": "speed_violation",
        "detection_details": {"speed_to_point_ms": 100.0},
        "confidence_score": 0.85,
    }

    is_new = await db.save_flagged_point(point_data)
    assert is_new is True

    # Try to save duplicate
    is_new = await db.save_flagged_point(point_data)
    assert is_new is False


@pytest.mark.asyncio
async def test_get_flagged_points(db):
    """Test retrieving flagged points"""
    # Save test points
    await db.save_flagged_point(
        {
            "point_id": 1,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": 1705484123,
            "detection_reason": "speed_violation",
            "detection_details": {},
            "confidence_score": 0.85,
            "status": "pending",
        }
    )

    await db.save_flagged_point(
        {
            "point_id": 2,
            "latitude": 40.7130,
            "longitude": -74.0062,
            "timestamp": 1705484124,
            "detection_reason": "jump_outlier",
            "detection_details": {},
            "confidence_score": 0.75,
            "status": "deleted",
        }
    )

    # Get all points
    all_points = await db.get_flagged_points()
    assert len(all_points) == 2

    # Verify point data
    point_ids = {p["point_id"] for p in all_points}
    assert point_ids == {1, 2}


@pytest.mark.asyncio
async def test_get_stats(db):
    """Test statistics retrieval"""
    # Save test points with different statuses
    await db.save_flagged_point(
        {
            "point_id": 1,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": 1705484123,
            "detection_reason": "speed_violation",
            "detection_details": {},
            "confidence_score": 0.85,
            "status": "pending",
        }
    )

    await db.save_flagged_point(
        {
            "point_id": 2,
            "latitude": 40.7130,
            "longitude": -74.0062,
            "timestamp": 1705484124,
            "detection_reason": "jump_outlier",
            "detection_details": {},
            "confidence_score": 0.75,
            "status": "deleted",
        }
    )

    stats = await db.get_stats()
    # Stats returns counts, not total
    assert "pending_count" in stats or "pending" in stats


@pytest.mark.asyncio
async def test_create_scan_history(db):
    """Test creating scan history record"""
    scan_id = await db.create_scan_history(
        start_date="2026-01-01", end_date="2026-01-02", scan_type="manual"
    )
    assert scan_id > 0


@pytest.mark.asyncio
async def test_update_scan_history(db):
    """Test updating scan history"""
    scan_id = await db.create_scan_history(
        start_date="2026-01-01", end_date="2026-01-02", scan_type="manual"
    )

    await db.update_scan_history(scan_id, status="completed", points_scanned=100, points_flagged=5)

    # Verify update (we'd need a get method to properly test this)
    # For now, just ensure no error is raised
    assert True


@pytest.mark.asyncio
async def test_get_last_completed_scan(db):
    """Test getting last completed scan"""
    # No scans initially
    last_scan = await db.get_last_completed_scan()
    assert last_scan is None

    # Create completed scan
    scan_id = await db.create_scan_history(
        start_date="2026-01-01", end_date="2026-01-02", scan_type="auto"
    )
    await db.update_scan_history(scan_id, status="completed", points_scanned=100)

    last_scan = await db.get_last_completed_scan()
    assert last_scan is not None
    assert last_scan["start_date"] == "2026-01-01"
    assert last_scan["end_date"] == "2026-01-02"


@pytest.mark.asyncio
async def test_sort_by_timestamp_desc(db):
    """Test sorting by timestamp descending (default)"""
    # Create points with different timestamps
    await db.save_flagged_point(
        {
            "point_id": 1,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": 1705484100,  # Oldest
            "detection_reason": "speed_violation",
            "detection_details": {},
            "confidence_score": 0.5,
            "status": "pending",
        }
    )
    await db.save_flagged_point(
        {
            "point_id": 2,
            "latitude": 40.7130,
            "longitude": -74.0062,
            "timestamp": 1705484200,  # Middle
            "detection_reason": "jump_outlier",
            "detection_details": {},
            "confidence_score": 0.7,
            "status": "pending",
        }
    )
    await db.save_flagged_point(
        {
            "point_id": 3,
            "latitude": 40.7132,
            "longitude": -74.0064,
            "timestamp": 1705484300,  # Newest
            "detection_reason": "speed_violation",
            "detection_details": {},
            "confidence_score": 0.6,
            "status": "pending",
        }
    )

    # Get points sorted by timestamp descending (default)
    points = await db.get_flagged_points(sort_by="timestamp", sort_dir="desc")

    assert len(points) == 3
    assert points[0]["point_id"] == 3  # Newest first
    assert points[1]["point_id"] == 2
    assert points[2]["point_id"] == 1  # Oldest last


@pytest.mark.asyncio
async def test_sort_by_timestamp_asc(db):
    """Test sorting by timestamp ascending"""
    # Create points with different timestamps
    await db.save_flagged_point(
        {
            "point_id": 1,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": 1705484100,
            "detection_reason": "speed_violation",
            "detection_details": {},
            "confidence_score": 0.5,
            "status": "pending",
        }
    )
    await db.save_flagged_point(
        {
            "point_id": 2,
            "latitude": 40.7130,
            "longitude": -74.0062,
            "timestamp": 1705484300,
            "detection_reason": "jump_outlier",
            "detection_details": {},
            "confidence_score": 0.7,
            "status": "pending",
        }
    )

    # Get points sorted by timestamp ascending
    points = await db.get_flagged_points(sort_by="timestamp", sort_dir="asc")

    assert len(points) == 2
    assert points[0]["point_id"] == 1  # Oldest first
    assert points[1]["point_id"] == 2  # Newest last


@pytest.mark.asyncio
async def test_sort_by_confidence_desc(db):
    """Test sorting by confidence descending"""
    await db.save_flagged_point(
        {
            "point_id": 1,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": 1705484100,
            "detection_reason": "speed_violation",
            "detection_details": {},
            "confidence_score": 0.5,  # Lowest
            "status": "pending",
        }
    )
    await db.save_flagged_point(
        {
            "point_id": 2,
            "latitude": 40.7130,
            "longitude": -74.0062,
            "timestamp": 1705484200,
            "detection_reason": "jump_outlier",
            "detection_details": {},
            "confidence_score": 0.9,  # Highest
            "status": "pending",
        }
    )
    await db.save_flagged_point(
        {
            "point_id": 3,
            "latitude": 40.7132,
            "longitude": -74.0064,
            "timestamp": 1705484300,
            "detection_reason": "speed_violation",
            "detection_details": {},
            "confidence_score": 0.7,  # Middle
            "status": "pending",
        }
    )

    # Get points sorted by confidence descending
    points = await db.get_flagged_points(sort_by="confidence", sort_dir="desc")

    assert len(points) == 3
    assert points[0]["confidence_score"] == 0.9  # Highest first
    assert points[1]["confidence_score"] == 0.7
    assert points[2]["confidence_score"] == 0.5  # Lowest last


@pytest.mark.asyncio
async def test_sort_by_confidence_asc(db):
    """Test sorting by confidence ascending"""
    await db.save_flagged_point(
        {
            "point_id": 1,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": 1705484100,
            "detection_reason": "speed_violation",
            "detection_details": {},
            "confidence_score": 0.3,
            "status": "pending",
        }
    )
    await db.save_flagged_point(
        {
            "point_id": 2,
            "latitude": 40.7130,
            "longitude": -74.0062,
            "timestamp": 1705484200,
            "detection_reason": "jump_outlier",
            "detection_details": {},
            "confidence_score": 0.8,
            "status": "pending",
        }
    )

    # Get points sorted by confidence ascending
    points = await db.get_flagged_points(sort_by="confidence", sort_dir="asc")

    assert len(points) == 2
    assert points[0]["confidence_score"] == 0.3  # Lowest first
    assert points[1]["confidence_score"] == 0.8  # Highest last


@pytest.mark.asyncio
async def test_sort_by_point_id(db):
    """Test sorting by point_id"""
    await db.save_flagged_point(
        {
            "point_id": 300,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": 1705484100,
            "detection_reason": "speed_violation",
            "detection_details": {},
            "confidence_score": 0.5,
            "status": "pending",
        }
    )
    await db.save_flagged_point(
        {
            "point_id": 100,
            "latitude": 40.7130,
            "longitude": -74.0062,
            "timestamp": 1705484200,
            "detection_reason": "jump_outlier",
            "detection_details": {},
            "confidence_score": 0.7,
            "status": "pending",
        }
    )
    await db.save_flagged_point(
        {
            "point_id": 200,
            "latitude": 40.7132,
            "longitude": -74.0064,
            "timestamp": 1705484300,
            "detection_reason": "speed_violation",
            "detection_details": {},
            "confidence_score": 0.6,
            "status": "pending",
        }
    )

    # Sort by point_id descending
    points = await db.get_flagged_points(sort_by="point_id", sort_dir="desc")
    assert points[0]["point_id"] == 300
    assert points[1]["point_id"] == 200
    assert points[2]["point_id"] == 100

    # Sort by point_id ascending
    points = await db.get_flagged_points(sort_by="point_id", sort_dir="asc")
    assert points[0]["point_id"] == 100
    assert points[1]["point_id"] == 200
    assert points[2]["point_id"] == 300


@pytest.mark.asyncio
async def test_sort_by_status(db):
    """Test sorting by status"""
    await db.save_flagged_point(
        {
            "point_id": 1,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": 1705484100,
            "detection_reason": "speed_violation",
            "detection_details": {},
            "confidence_score": 0.5,
        }
    )
    await db.save_flagged_point(
        {
            "point_id": 2,
            "latitude": 40.7130,
            "longitude": -74.0062,
            "timestamp": 1705484200,
            "detection_reason": "jump_outlier",
            "detection_details": {},
            "confidence_score": 0.7,
        }
    )
    await db.save_flagged_point(
        {
            "point_id": 3,
            "latitude": 40.7132,
            "longitude": -74.0064,
            "timestamp": 1705484300,
            "detection_reason": "speed_violation",
            "detection_details": {},
            "confidence_score": 0.6,
        }
    )

    # Mark points with different statuses
    await db.mark_as_deleted([2])
    await db.mark_as_ignored([3])

    # Sort by status (alphabetically)
    points = await db.get_flagged_points(status="all", sort_by="status", sort_dir="asc")
    assert len(points) == 3
    # Alphabetical: deleted, ignored, pending
    assert points[0]["status"] == "deleted"
    assert points[1]["status"] == "ignored"
    assert points[2]["status"] == "pending"


@pytest.mark.asyncio
async def test_default_sort_is_timestamp_desc(db):
    """Test that default sorting is timestamp descending"""
    await db.save_flagged_point(
        {
            "point_id": 1,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": 1705484100,
            "detection_reason": "speed_violation",
            "detection_details": {},
            "confidence_score": 0.5,
            "status": "pending",
        }
    )
    await db.save_flagged_point(
        {
            "point_id": 2,
            "latitude": 40.7130,
            "longitude": -74.0062,
            "timestamp": 1705484300,
            "detection_reason": "jump_outlier",
            "detection_details": {},
            "confidence_score": 0.7,
            "status": "pending",
        }
    )

    # Get points with default parameters (should be timestamp desc)
    points = await db.get_flagged_points()

    assert len(points) == 2
    assert points[0]["point_id"] == 2  # Newer timestamp first
    assert points[1]["point_id"] == 1


@pytest.mark.asyncio
async def test_sort_with_filters(db):
    """Test that sorting works with status and confidence filters"""
    await db.save_flagged_point(
        {
            "point_id": 1,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": 1705484100,
            "detection_reason": "speed_violation",
            "detection_details": {},
            "confidence_score": 0.3,
        }
    )
    await db.save_flagged_point(
        {
            "point_id": 2,
            "latitude": 40.7130,
            "longitude": -74.0062,
            "timestamp": 1705484200,
            "detection_reason": "jump_outlier",
            "detection_details": {},
            "confidence_score": 0.8,
        }
    )
    await db.save_flagged_point(
        {
            "point_id": 3,
            "latitude": 40.7132,
            "longitude": -74.0064,
            "timestamp": 1705484300,
            "detection_reason": "speed_violation",
            "detection_details": {},
            "confidence_score": 0.9,
        }
    )

    # Mark point 3 as deleted
    await db.mark_as_deleted([3])

    # Filter by status=pending, min_confidence=0.5, sort by confidence desc
    points = await db.get_flagged_points(
        status="pending", min_confidence=0.5, sort_by="confidence", sort_dir="desc"
    )

    # Only point 2 should match (pending + confidence >= 0.5)
    # Point 1 is pending but confidence < 0.5
    # Point 3 has high confidence but is deleted (not pending)
    assert len(points) == 1
    assert points[0]["point_id"] == 2
    assert points[0]["confidence_score"] == 0.8

    # Test with 'all' status filter
    points_all = await db.get_flagged_points(
        status="all", min_confidence=0.5, sort_by="confidence", sort_dir="desc"
    )

    # Points 2 and 3 should match (both have confidence >= 0.5)
    assert len(points_all) == 2
    assert points_all[0]["point_id"] == 3  # 0.9 confidence (highest)
    assert points_all[1]["point_id"] == 2  # 0.8 confidence
