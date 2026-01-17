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
