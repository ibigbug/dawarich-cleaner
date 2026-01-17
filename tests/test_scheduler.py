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

    # Mock DawarichService to prevent actual HTTP calls
    with patch("app.services.scheduler.DawarichService") as mock_dawarich_class:
        mock_dawarich = MagicMock()
        mock_dawarich.fetch_points = AsyncMock(return_value=[])
        mock_dawarich_class.return_value = mock_dawarich

        with patch("app.services.scheduler.detect_outliers", return_value=[]):
            await scheduler._run_scan()

    # Should have marked the stuck scan as failed
    assert mock_db.update_scan_history.call_count >= 1
    # Find the call that marked it as failed
    failed_call = None
    for call in mock_db.update_scan_history.call_args_list:
        if call[1].get("status") == "failed":
            failed_call = call
            break

    assert failed_call is not None
    assert failed_call[0][0] == 1  # scan_id


@pytest.mark.asyncio
async def test_scheduler_skips_small_time_range(mock_db):
    """Test that scheduler skips if time range is too small"""
    # No running scan
    mock_db.get_last_scan = AsyncMock(return_value=None)

    # Use a timestamp that's very recent (1 minute ago)
    # This will create a very small time range
    recent_timestamp = (datetime.now() - timedelta(minutes=1)).timestamp()
    mock_db.get_last_completed_scan = AsyncMock(
        return_value={
            "id": 1,
            "end_date": datetime.now().strftime("%Y-%m-%d"),
            "completed_at": recent_timestamp,
        }
    )

    scheduler = AutoScanScheduler(mock_db)

    # This should skip because time range is < 2 minutes
    # (1 min ago - 5 min overlap = started 6 min ago, but completed_at is 1 min ago)
    # Actually: start = completed_at (1 min ago) - 5 min = 6 min ago
    # end = now, so range = 6 min - that's NOT small.
    # Let me use a more recent timestamp
    very_recent = (datetime.now() - timedelta(seconds=30)).timestamp()
    mock_db.get_last_completed_scan = AsyncMock(
        return_value={
            "id": 1,
            "end_date": datetime.now().strftime("%Y-%m-%d"),
            "completed_at": very_recent,
        }
    )

    # Range will be: (30 sec ago - 5 min) to now = about 4.5 min, which is > 2 min
    # So this won't trigger the skip. Let's use completed_at that's even more recent.
    # Actually, if completed 10 seconds ago: start = 10sec - 5min = -4min50sec ago
    # That means start is in the future? No, 10sec ago - 5min = 5min10sec ago
    # Range = 5min10sec, still > 2min.

    # To get <2min range, completed_at needs to be very recent
    # If completed 1 second ago: start = 1sec - 5min = 5min1sec ago, range = 5min > 2min
    # The overlap is the problem. With 5 min overlap, we always get >2min range.

    # Actually looking at the code: start = completed_at - 5min, end = now
    # For range < 2min: (now - (completed_at - 5min)) < 120
    # now - completed_at + 5min < 120
    # now - completed_at < -180 (impossible, as now > completed_at)

    # So the small time range check can only trigger if start > end somehow
    # Or if completed_at is None and fallback is used

    # Let's test the None case
    mock_db.get_last_completed_scan = AsyncMock(
        return_value={
            "id": 1,
            "end_date": (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d"),
            "completed_at": None,  # No timestamp
        }
    )

    await scheduler._run_scan()

    # Should check for last scan, then get last completed
    mock_db.get_last_scan.assert_called_once()
    mock_db.get_last_completed_scan.assert_called_once()
    # Should not create new scan history if time range too small
    # (fallback sets start to tomorrow 23:59:59, which is > now)
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
