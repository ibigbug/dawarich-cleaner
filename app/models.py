"""SQLAlchemy ORM models"""

from sqlalchemy import Column, Integer, Float, String, Text, Index, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class FlaggedPoint(Base):
    """Flagged GPS point that may be an outlier"""

    __tablename__ = "flagged_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    point_id = Column(Integer, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timestamp = Column(Integer, nullable=False)
    detection_reason = Column(String, nullable=False)
    detection_details = Column(Text)
    confidence_score = Column(Float, default=0.5)
    status = Column(String, default="pending")
    previous_point_id = Column(Integer)
    next_point_id = Column(Integer)
    stay_location_lat = Column(Float)
    stay_location_lon = Column(Float)
    flagged_at = Column(Integer, server_default=func.strftime("%s", "now"))
    reviewed_at = Column(Integer)

    __table_args__ = (
        Index("idx_status", "status"),
        Index("idx_confidence", "confidence_score"),
        Index("idx_point_detection", "point_id", "detection_reason", unique=True),
    )


class ScanHistory(Base):
    """History of outlier detection scans"""

    __tablename__ = "scan_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    started_at = Column(Integer, server_default=func.strftime("%s", "now"))
    completed_at = Column(Integer)
    status = Column(String, default="running")
    points_scanned = Column(Integer, default=0)
    points_flagged = Column(Integer, default=0)
    error_message = Column(Text)
    scan_type = Column(String, default="manual")
