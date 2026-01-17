"""Database module using SQLAlchemy ORM"""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base, FlaggedPoint, ScanHistory


class Database:
    """Database handler using SQLAlchemy ORM - supports SQLite and PostgreSQL"""

    def __init__(self, database_url: str):
        self.database_url = database_url

        # Configure engine options based on database type
        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}

        self.engine = create_async_engine(
            database_url,
            echo=False,
            connect_args=connect_args,
        )
        self.async_session = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        """Initialize database schema"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_stats(self) -> dict[str, Any]:
        """Get dashboard statistics"""
        async with self.async_session() as session:
            # Count by status
            stmt = select(
                func.count().filter(FlaggedPoint.status == "pending").label("pending"),
                func.count().filter(FlaggedPoint.status == "deleted").label("deleted"),
                func.count().filter(FlaggedPoint.status == "ignored").label("ignored"),
                func.count().label("total_flagged"),
            ).select_from(FlaggedPoint)

            result = await session.execute(stmt)
            row = result.one()

            # Get last scan
            last_scan_stmt = (
                select(ScanHistory.started_at)
                .where(ScanHistory.status == "completed")
                .order_by(ScanHistory.started_at.desc())
                .limit(1)
            )
            last_scan_result = await session.execute(last_scan_stmt)
            last_scan_row = last_scan_result.scalar_one_or_none()

            return {
                "pending": row.pending or 0,
                "deleted": row.deleted or 0,
                "ignored": row.ignored or 0,
                "total_flagged": row.total_flagged or 0,
                "last_scan": (
                    datetime.fromtimestamp(last_scan_row).strftime("%Y-%m-%d %H:%M")
                    if last_scan_row
                    else "Never"
                ),
            }

    async def get_flagged_points(
        self,
        status: str = "pending",
        min_confidence: float = 0.0,
        sort_by: str = "timestamp",
        sort_dir: str = "desc",
    ) -> list[dict[str, Any]]:
        """Get flagged points by status and confidence threshold"""
        async with self.async_session() as session:
            stmt = select(FlaggedPoint).where(FlaggedPoint.confidence_score >= min_confidence)

            # Add status filter only if not 'all'
            if status and status != "all":
                stmt = stmt.where(FlaggedPoint.status == status)

            # Apply sorting
            sort_column = {
                "timestamp": FlaggedPoint.timestamp,
                "confidence": FlaggedPoint.confidence_score,
                "point_id": FlaggedPoint.point_id,
                "status": FlaggedPoint.status,
            }.get(sort_by, FlaggedPoint.timestamp)

            if sort_dir == "asc":
                stmt = stmt.order_by(sort_column.asc())
            else:
                stmt = stmt.order_by(sort_column.desc())

            result = await session.execute(stmt)
            points = result.scalars().all()

            return [
                {
                    "id": point.id,
                    "point_id": point.point_id,
                    "latitude": point.latitude,
                    "longitude": point.longitude,
                    "timestamp": point.timestamp,
                    "timestamp_str": datetime.fromtimestamp(point.timestamp).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "detection_reason": point.detection_reason,
                    "detection_details": (
                        json.loads(point.detection_details) if point.detection_details else {}
                    ),
                    "detection_details_parsed": (
                        json.loads(point.detection_details) if point.detection_details else {}
                    ),
                    "confidence_score": point.confidence_score,
                    "status": point.status,
                    "previous_point_id": point.previous_point_id,
                    "next_point_id": point.next_point_id,
                    "stay_location_lat": point.stay_location_lat,
                    "stay_location_lon": point.stay_location_lon,
                    "timestamp_url_start": point.timestamp - 3600,  # 1 hour before
                    "timestamp_url_end": point.timestamp + 3600,  # 1 hour after
                }
                for point in points
            ]

    async def save_flagged_point(self, point: dict[str, Any]) -> bool:
        """Save a flagged point. Returns True if new, False if duplicate"""
        async with self.async_session() as session:
            try:
                flagged_point = FlaggedPoint(
                    point_id=point["point_id"],
                    latitude=point["latitude"],
                    longitude=point["longitude"],
                    timestamp=point["timestamp"],
                    detection_reason=point["detection_reason"],
                    detection_details=json.dumps(point.get("detection_details", {})),
                    confidence_score=point.get("confidence_score", 0.5),
                    previous_point_id=point.get("previous_point_id"),
                    next_point_id=point.get("next_point_id"),
                )
                session.add(flagged_point)
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False

    async def mark_as_deleted(self, point_ids: list[int]):
        """Mark points as deleted"""
        async with self.async_session() as session:
            stmt = (
                update(FlaggedPoint)
                .where(FlaggedPoint.point_id.in_(point_ids))
                .values(
                    status="deleted",
                    reviewed_at=func.strftime("%s", "now"),
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def mark_as_restored(self, point_ids: list[int]):
        """Mark points as restored"""
        async with self.async_session() as session:
            stmt = (
                update(FlaggedPoint)
                .where(FlaggedPoint.point_id.in_(point_ids))
                .values(status="pending", reviewed_at=None)
            )
            await session.execute(stmt)
            await session.commit()

    async def mark_as_ignored(self, point_ids: list[int]):
        """Mark points as ignored"""
        async with self.async_session() as session:
            stmt = (
                update(FlaggedPoint)
                .where(FlaggedPoint.point_id.in_(point_ids))
                .values(
                    status="ignored",
                    reviewed_at=func.strftime("%s", "now"),
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def remove_flagged_points(self, point_ids: list[int]):
        """Permanently remove flagged points from database"""
        async with self.async_session() as session:
            stmt = delete(FlaggedPoint).where(FlaggedPoint.point_id.in_(point_ids))
            await session.execute(stmt)
            await session.commit()

    async def create_scan_history(
        self, start_date: str, end_date: str, scan_type: str = "manual"
    ) -> int:
        """Create scan history record"""
        async with self.async_session() as session:
            scan = ScanHistory(
                start_date=start_date,
                end_date=end_date,
                scan_type=scan_type,
            )
            session.add(scan)
            await session.commit()
            await session.refresh(scan)
            return scan.id

    async def update_scan_history(
        self,
        scan_id: int,
        status: str,
        points_scanned: int = 0,
        points_flagged: int = 0,
        error_message: str | None = None,
    ):
        """Update scan history with results"""
        async with self.async_session() as session:
            stmt = (
                update(ScanHistory)
                .where(ScanHistory.id == scan_id)
                .values(
                    status=status,
                    completed_at=func.strftime("%s", "now"),
                    points_scanned=points_scanned,
                    points_flagged=points_flagged,
                    error_message=error_message,
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def get_last_scan(self) -> dict[str, Any] | None:
        """Get the most recent scan (any status)"""
        async with self.async_session() as session:
            stmt = select(ScanHistory).order_by(ScanHistory.started_at.desc()).limit(1)
            result = await session.execute(stmt)
            scan = result.scalar_one_or_none()

            if not scan:
                return None

            return {
                "id": scan.id,
                "status": scan.status,
                "started_at": scan.started_at,
                "start_date": scan.start_date,
                "end_date": scan.end_date,
            }

    async def get_last_completed_scan(self) -> dict[str, Any] | None:
        """Get the most recent completed scan"""
        async with self.async_session() as session:
            stmt = (
                select(ScanHistory)
                .where(ScanHistory.status == "completed")
                .order_by(ScanHistory.completed_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            scan = result.scalar_one_or_none()

            if not scan:
                return None

            return {
                "id": scan.id,
                "start_date": scan.start_date,
                "end_date": scan.end_date,
                "completed_at": scan.completed_at,
                "points_scanned": scan.points_scanned,
                "points_flagged": scan.points_flagged,
            }

    async def close(self):
        """Close database connection"""
        await self.engine.dispose()
