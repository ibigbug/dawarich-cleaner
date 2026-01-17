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

    # Mock last completed to be far in future to make time range small
    future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    mock_db.get_last_completed_scan = AsyncMock(
        return_value={
            "id": 2,
            "end_date": future_date,
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
    # Should not try to create a new scan (time range too small)
    mock_db.create_scan_history.assert_not_called()


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


@pytest.mark.asyncio
async def test_scheduler_uses_completion_timestamp():
    """Test that scheduler uses completion timestamp from last scan to avoid rescanning same dates"""
    mock_db = MagicMock()
    mock_db.get_last_scan = AsyncMock(return_value=None)

    # Last scan completed 12 minutes ago
    completed_timestamp = (datetime.now() - timedelta(minutes=12)).timestamp()
    mock_db.get_last_completed_scan = AsyncMock(
        return_value={
            "id": 1,
            "end_date": "2026-01-16",  # Date-only string (would be midnight)
            "completed_at": completed_timestamp,  # Actual completion time
        }
    )

    mock_db.create_scan_history = AsyncMock(return_value=2)
    mock_db.update_scan_history = AsyncMock()
    mock_db.save_flagged_point = AsyncMock(return_value=True)

    with patch("app.services.scheduler.DawarichService") as mock_dawarich_class:
        mock_dawarich = MagicMock()
        mock_dawarich.fetch_points = AsyncMock(return_value=[])
        mock_dawarich_class.return_value = mock_dawarich

        with patch("app.services.scheduler.detect_outliers", return_value=[]):
            scheduler = AutoScanScheduler(mock_db)
            await scheduler._run_scan()

            # Verify scan was created
            mock_db.create_scan_history.assert_called_once()

            # Get the call args to verify dates
            call_kwargs = mock_db.create_scan_history.call_args[1]
            start_date_str = call_kwargs["start_date"]

            # Start date should be based on completed_at (12 min ago - 5 min overlap = 17 min ago)
            # NOT based on end_date string "2026-01-16" which would parse to midnight
            # So start_date should be TODAY (not 2026-01-16)
            expected_date = datetime.now().strftime("%Y-%m-%d")
            assert start_date_str == expected_date, (
                f"Expected start_date to be {expected_date} based on completion timestamp, "
                f"but got {start_date_str}"
            )


@pytest.mark.asyncio
async def test_scheduler_first_scan_uses_15_minutes():
    """Test that first scan only looks back 15 minutes, not 24 hours"""
    mock_db = MagicMock()
    mock_db.get_last_scan = AsyncMock(return_value=None)
    mock_db.get_last_completed_scan = AsyncMock(return_value=None)  # No previous scans
    mock_db.create_scan_history = AsyncMock(return_value=1)
    mock_db.update_scan_history = AsyncMock()

    with patch("app.services.scheduler.DawarichService") as mock_dawarich_class:
        mock_dawarich = MagicMock()
        mock_dawarich.fetch_points = AsyncMock(return_value=[])
        mock_dawarich_class.return_value = mock_dawarich

        with patch("app.services.scheduler.detect_outliers", return_value=[]):
            scheduler = AutoScanScheduler(mock_db)
            await scheduler._run_scan()

            # Verify scan was created
            mock_db.create_scan_history.assert_called_once()

            # Get the call args to check the date range
            call_kwargs = mock_db.create_scan_history.call_args[1]
            start_date_str = call_kwargs["start_date"]
            end_date_str = call_kwargs["end_date"]

            # Both should be today (15 minutes ago is still today)
            today = datetime.now().strftime("%Y-%m-%d")
            assert start_date_str == today, (
                f"First scan should start from today (15 min ago), got {start_date_str}"
            )
            assert end_date_str == today, f"First scan should end today, got {end_date_str}"
