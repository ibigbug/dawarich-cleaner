"""Tests for the AutoScanScheduler"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.scheduler import AutoScanScheduler


@pytest.fixture
def mock_db():
    """Mock Database for testing"""
    db = MagicMock()
    db.get_last_scan = AsyncMock(return_value=None)
    db.get_last_completed_scan = AsyncMock(return_value=None)
    db.create_scan_history = AsyncMock(return_value=1)
    db.update_scan_history = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_scheduler_initialization(mock_db):
    """Test scheduler initialization"""
    scheduler = AutoScanScheduler(mock_db)
    assert scheduler.db == mock_db
    assert scheduler._running is False
    assert scheduler.task is None


@pytest.mark.asyncio
async def test_scheduler_skip_if_running(mock_db):
    """Test that scheduler skips if scan is already running"""
    # Mock a scan currently running (recent timestamp)
    mock_db.get_last_scan = AsyncMock(
        return_value={
            "id": 1,
            "status": "running",
            "started_at": datetime.now().timestamp(),
        }
    )

    scheduler = AutoScanScheduler(mock_db)
    await scheduler._run_scan()

    # Should only check for last scan and return early
    mock_db.get_last_scan.assert_called_once()
    # Should not try to get last completed scan
    mock_db.get_last_completed_scan.assert_not_called()


@pytest.mark.asyncio
async def test_scheduler_detects_stuck_scan(mock_db):
    """Test that scheduler detects and marks stuck scans as failed"""
    # Mock a scan that's been running for 2 hours (stuck)
    old_timestamp = (datetime.now() - timedelta(hours=2)).timestamp()
    mock_db.get_last_scan = AsyncMock(
        return_value={"id": 1, "status": "running", "started_at": old_timestamp}
    )

    # After marking as failed, it will try to scan, so mock small time range to skip
    mock_db.get_last_completed_scan = AsyncMock(
        return_value={
            "id": 2,
            "end_date": datetime.now().strftime(
                "%Y-%m-%d"
            ),  # Today - will skip (time range too small)
            "completed_at": datetime.now().timestamp(),
        }
    )

    scheduler = AutoScanScheduler(mock_db)
    await scheduler._run_scan()

    # Should have marked the stuck scan as failed
    mock_db.update_scan_history.assert_called_once()
    call_args = mock_db.update_scan_history.call_args
    assert call_args[0][0] == 1  # scan_id
    assert call_args[1]["status"] == "failed"


@pytest.mark.asyncio
async def test_scheduler_skips_small_time_range(mock_db):
    """Test that scheduler skips if time range is too small"""
    # No running scan
    mock_db.get_last_scan = AsyncMock(return_value=None)

    # Last completed scan ended just 1 minute ago
    # The code parses end_date as midnight, so we need end_date to be today
    # which means start_date will be today 00:00 - 5 minutes = yesterday 23:55
    # That's NOT a small time range. We need to use a time VERY close to now.
    # Actually, the issue is that end_date is just a date string, not datetime.
    # When parsed with strptime, it becomes midnight.
    # So to make time range small, we need yesterday's date as end_date
    # Then start_date = yesterday 00:00 - 5 min = 2 days ago 23:55
    # and end_date (now) = today, which is > 24 hours = not small.
    #
    # Actually to make it small, we should return today as end_date,
    # BUT also make "now" be very early in the day (close to midnight).
    # Actually, let's just verify it doesn't create a scan.
    # Since time calculation is complex, let's test it differently.

    # Use a date FAR in the future for end_date to trigger small range
    future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    mock_db.get_last_completed_scan = AsyncMock(
        return_value={
            "id": 1,
            "end_date": future_date,  # Future date
            "completed_at": datetime.now().timestamp(),
        }
    )

    scheduler = AutoScanScheduler(mock_db)

    # This should skip because future_date 00:00 - 5 min is in the future
    # and (now - future_time) is negative, definitely < 120 seconds
    await scheduler._run_scan()

    # Should check for last scan, then get last completed
    mock_db.get_last_scan.assert_called_once()
    mock_db.get_last_completed_scan.assert_called_once()
    # Should not create new scan history if time range too small
    mock_db.create_scan_history.assert_not_called()


@pytest.mark.asyncio
async def test_scheduler_first_scan():
    """Test first scan when no previous scans exist"""
    mock_db = MagicMock()
    mock_db.get_last_scan = AsyncMock(return_value=None)
    mock_db.get_last_completed_scan = AsyncMock(return_value=None)
    mock_db.create_scan_history = AsyncMock(return_value=1)
    mock_db.update_scan_history = AsyncMock()

    # Mock DawarichService to prevent API calls
    with patch("app.services.scheduler.DawarichService") as mock_dawarich_class:
        mock_dawarich = MagicMock()
        mock_dawarich.fetch_points = AsyncMock(return_value=[])
        mock_dawarich_class.return_value = mock_dawarich

        # Mock detect_outliers
        with patch("app.services.scheduler.detect_outliers", return_value=[]):
            scheduler = AutoScanScheduler(mock_db)
            await scheduler._run_scan()

            # Should create scan history for first scan
            assert mock_db.create_scan_history.call_count >= 1
            # Should update scan history as completed
            assert mock_db.update_scan_history.call_count >= 1
