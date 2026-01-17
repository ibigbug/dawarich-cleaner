"""Background scheduler for automated scans"""

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta

from ..config import get_settings
from ..database import Database
from .dawarich import DawarichService
from .outlier_detector import detect_outliers

logger = logging.getLogger(__name__)


class AutoScanScheduler:
    """Runs automated scans every 10 minutes"""

    def __init__(self, db: Database):
        self.db = db
        self.settings = get_settings()
        self.task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        """Start the background scheduler"""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self.task = asyncio.create_task(self._run_loop())
        logger.info("🤖 Auto-scan scheduler started (every 10 minutes)")

    async def stop(self):
        """Stop the background scheduler"""
        self._running = False
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        logger.info("🛑 Auto-scan scheduler stopped")

    async def _run_loop(self):
        """Main loop that runs scans periodically"""
        while self._running:
            try:
                await self._run_scan()
            except Exception as e:
                logger.error(f"Error in auto-scan: {e}", exc_info=True)

            # Wait 10 minutes before next scan
            try:
                await asyncio.sleep(600)  # 10 minutes = 600 seconds
            except asyncio.CancelledError:
                break

    async def _run_scan(self):
        """Run a single automated scan"""
        # Check if there's an in-progress scan
        last_scan = await self.db.get_last_scan()
        if last_scan and last_scan.get("status") == "running":
            # Check if the scan has been running for too long (stale/stuck)
            started_at = last_scan.get("started_at")
            if started_at:
                time_running = datetime.now().timestamp() - started_at
                # If running for more than 30 minutes, consider it stuck/failed
                if time_running > 1800:  # 30 minutes
                    logger.warning(
                        f"⚠️  Found stuck scan (running for {time_running / 60:.0f} min), marking as failed"
                    )
                    await self.db.update_scan_history(
                        last_scan["id"],
                        status="failed",
                        error_message="Scan timed out (exceeded 30 minutes)",
                    )
                else:
                    logger.info("⏸️  Skipping auto-scan: Another scan is in progress")
                    return

        # Get the last completed scan time
        last_completed = await self.db.get_last_completed_scan()

        if last_completed:
            # Parse the end_date string (format: "YYYY-MM-DD") and add 5 min overlap
            end_date_str = last_completed["end_date"]
            last_scan_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            start_date = last_scan_date - timedelta(minutes=5)
            logger.info(f"📅 Auto-scan from last scan: {start_date.strftime('%Y-%m-%d %H:%M')}")
        else:
            # First scan - scan last 24 hours
            start_date = datetime.now() - timedelta(hours=24)
            logger.info("📅 First auto-scan: scanning last 24 hours")

        end_date = datetime.now()

        # Don't scan if the time range is too small (less than 2 minutes)
        time_range = (end_date - start_date).total_seconds()
        if time_range < 120:
            logger.info(f"⏸️  Skipping auto-scan: Time range too small ({time_range:.0f}s)")
            return

        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        logger.info(f"🔍 Auto-scan: {start_date_str} to {end_date_str}")

        # Create scan history record
        scan_id = await self.db.create_scan_history(
            start_date=start_date_str,
            end_date=end_date_str,
            scan_type="auto",
        )

        try:
            # Fetch points from Dawarich
            dawarich = DawarichService(
                self.settings.dawarich_api_url, self.settings.dawarich_api_key
            )
            points = await dawarich.fetch_points(start_date_str, end_date_str, "UTC")

            if not points:
                logger.info("✅ Auto-scan: No points found")
                await self.db.update_scan_history(
                    scan_id, status="completed", points_scanned=0, points_flagged=0
                )
                return

            logger.info(f"📊 Auto-scan: Analyzing {len(points)} points")

            # Use default thresholds: 30 m/s (108 km/h), 500m distance
            outliers = detect_outliers(points, max_speed_ms=30, max_distance_m=500)

            logger.info(f"🚩 Auto-scan: Found {len(outliers)} potential outliers")

            # Save new outliers (skip duplicates automatically)
            new_count = 0
            for outlier in outliers:
                is_new = await self.db.save_flagged_point(outlier)
                if is_new:
                    new_count += 1

            # Update scan history
            await self.db.update_scan_history(
                scan_id,
                status="completed",
                points_scanned=len(points),
                points_flagged=new_count,
            )

            logger.info(f"✅ Auto-scan complete: {new_count} new outliers flagged")
            if new_count < len(outliers):
                logger.info(f"   (Skipped {len(outliers) - new_count} duplicates)")

        except Exception as e:
            logger.error(f"❌ Error during auto-scan: {e}", exc_info=True)
            await self.db.update_scan_history(scan_id, status="failed", error_message=str(e))
            raise
