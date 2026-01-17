"""
Database helper module for D1 operations
Clean abstraction over D1 database queries
"""
import json
from datetime import datetime
from typing import List, Dict, Optional, Any


class Database:
    """Database helper for D1 operations"""
    
    def __init__(self, db):
        """
        Initialize database helper
        
        Args:
            db: D1 database binding from env
        """
        self.db = db
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get dashboard statistics"""
        query = """
        SELECT 
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
            COUNT(CASE WHEN status = 'deleted' THEN 1 END) as deleted,
            COUNT(CASE WHEN status = 'ignored' THEN 1 END) as ignored,
            COUNT(*) as total_flagged
        FROM flagged_points
        """
        result = await self.db.prepare(query).first()
        
        # Get last scan
        last_scan_query = """
        SELECT started_at FROM scan_history 
        WHERE status = 'completed' 
        ORDER BY started_at DESC LIMIT 1
        """
        last_scan = await self.db.prepare(last_scan_query).first()
        
        return {
            'pending': result.pending if result else 0,
            'deleted': result.deleted if result else 0,
            'ignored': result.ignored if result else 0,
            'total_flagged': result.total_flagged if result else 0,
            'last_scan': datetime.fromtimestamp(last_scan.started_at).strftime('%Y-%m-%d %H:%M') 
                        if last_scan else 'Never'
        }
    
    async def get_pending_points(self, timezone='UTC', min_confidence=0.0) -> List[Dict[str, Any]]:
        """Get all pending flagged points above confidence threshold"""
        query = """
        SELECT id, point_id, latitude, longitude, timestamp, 
               detection_reason, detection_details, confidence_score,
               previous_point_id, next_point_id,
               stay_location_lat, stay_location_lon
        FROM flagged_points 
        WHERE status = 'pending' AND confidence_score >= ?
        ORDER BY confidence_score DESC, timestamp DESC
        """
        result = await self.db.prepare(query).bind(min_confidence).all()
        points = result.results if result else []
        
        # Convert JsProxy objects to Python dicts and add formatted timestamp
        python_points = []
        for point in points:
            # Parse detection_details JSON
            details_parsed = {}
            try:
                details_parsed = json.loads(point.detection_details)
            except:
                details_parsed = {}
            
            python_point = {
                'id': point.id,
                'point_id': point.point_id,
                'latitude': point.latitude,
                'longitude': point.longitude,
                'timestamp': point.timestamp,
                'detection_reason': point.detection_reason,
                'detection_details': point.detection_details,
                'detection_details_parsed': details_parsed,
                'confidence_score': point.confidence_score,
                'previous_point_id': point.previous_point_id,
                'next_point_id': point.next_point_id,
                'stay_location_lat': point.stay_location_lat,
                'stay_location_lon': point.stay_location_lon,
                'timestamp_str': datetime.fromtimestamp(point.timestamp).strftime('%Y-%m-%d %H:%M:%S UTC'),
                'timestamp_url': datetime.fromtimestamp(point.timestamp).strftime('%Y-%m-%dT%H:%M:%S'),
                'timestamp_url_start': datetime.fromtimestamp(point.timestamp - 5).strftime('%Y-%m-%dT%H:%M:%S'),
                'timestamp_url_end': datetime.fromtimestamp(point.timestamp + 5).strftime('%Y-%m-%dT%H:%M:%S')
            }
            python_points.append(python_point)
        
        return python_points
    
    async def get_deleted_points(self, min_confidence=0.0) -> List[Dict[str, Any]]:
        """Get deleted/ignored points that can be restored"""
        query = """
        SELECT id, point_id, latitude, longitude, timestamp, 
               detection_reason, detection_details, confidence_score,
               status, reviewed_at
        FROM flagged_points 
        WHERE status IN ('deleted', 'ignored') AND confidence_score >= ?
        ORDER BY reviewed_at DESC
        LIMIT 100
        """
        result = await self.db.prepare(query).bind(min_confidence).all()
        points = result.results if result else []
        
        # Convert JsProxy objects to Python dicts
        python_points = []
        for point in points:
            # Parse detection_details JSON
            details_parsed = {}
            try:
                details_parsed = json.loads(point.detection_details)
            except:
                details_parsed = {}
            
            python_point = {
                'id': point.id,
                'point_id': point.point_id,
                'latitude': point.latitude,
                'longitude': point.longitude,
                'timestamp': point.timestamp,
                'detection_reason': point.detection_reason,
                'detection_details_parsed': details_parsed,
                'confidence_score': point.confidence_score,
                'status': point.status,
                'timestamp_str': datetime.fromtimestamp(point.timestamp).strftime('%Y-%m-%d %H:%M:%S UTC')
            }
            python_points.append(python_point)
        
        return python_points
    
    async def get_points_by_status(self, status='pending', min_confidence=0.0) -> List[Dict[str, Any]]:
        """Get points filtered by status and confidence threshold"""
        if status == 'all':
            query = """
            SELECT id, point_id, latitude, longitude, timestamp, 
                   detection_reason, detection_details, confidence_score,
                   previous_point_id, next_point_id,
                   stay_location_lat, stay_location_lon, status, reviewed_at
            FROM flagged_points 
            WHERE confidence_score >= ?
            ORDER BY confidence_score DESC, timestamp DESC
            LIMIT 1000
            """
        else:
            query = """
            SELECT id, point_id, latitude, longitude, timestamp, 
                   detection_reason, detection_details, confidence_score,
                   previous_point_id, next_point_id,
                   stay_location_lat, stay_location_lon, status, reviewed_at
            FROM flagged_points 
            WHERE status = ? AND confidence_score >= ?
            ORDER BY confidence_score DESC, timestamp DESC
            LIMIT 1000
            """
        
        if status == 'all':
            result = await self.db.prepare(query).bind(min_confidence).all()
        else:
            result = await self.db.prepare(query).bind(status, min_confidence).all()
        
        points = result.results if result else []
        
        # Convert JsProxy objects to Python dicts
        python_points = []
        for point in points:
            # Parse detection_details JSON
            details_parsed = {}
            try:
                details_parsed = json.loads(point.detection_details)
            except:
                details_parsed = {}
            
            python_point = {
                'id': point.id,
                'point_id': point.point_id,
                'latitude': point.latitude,
                'longitude': point.longitude,
                'timestamp': point.timestamp,
                'detection_reason': point.detection_reason,
                'detection_details': point.detection_details,
                'detection_details_parsed': details_parsed,
                'confidence_score': point.confidence_score,
                'previous_point_id': point.previous_point_id,
                'next_point_id': point.next_point_id,
                'stay_location_lat': point.stay_location_lat,
                'stay_location_lon': point.stay_location_lon,
                'status': point.status,
                'timestamp_str': datetime.fromtimestamp(point.timestamp).strftime('%Y-%m-%d %H:%M:%S UTC'),
                'timestamp_url': datetime.fromtimestamp(point.timestamp).strftime('%Y-%m-%dT%H:%M:%S'),
                'timestamp_url_start': datetime.fromtimestamp(point.timestamp - 5).strftime('%Y-%m-%dT%H:%M:%S'),
                'timestamp_url_end': datetime.fromtimestamp(point.timestamp + 5).strftime('%Y-%m-%dT%H:%M:%S')
            }
            python_points.append(python_point)
        
        return python_points
    
    async def create_scan_history(self, start_date: str, end_date: str, scan_type: str) -> int:
        """
        Create a new scan history record
        
        Returns:
            scan_id: ID of created scan record
        """
        now = int(datetime.now().timestamp())
        result = await self.db.prepare("""
            INSERT INTO scan_history (start_date, end_date, scan_type, status, started_at, created_at)
            VALUES (?, ?, ?, 'running', ?, ?)
        """).bind(start_date, end_date, scan_type, now, now).run()
        
        return result.meta.last_row_id
    
    async def update_scan_history(
        self, 
        scan_id: int, 
        status: str,
        points_scanned: int = 0,
        points_flagged: int = 0,
        error_message: Optional[str] = None
    ):
        """Update scan history record"""
        now = int(datetime.now().timestamp())
        
        if error_message:
            await self.db.prepare("""
                UPDATE scan_history 
                SET status = ?, error_message = ?, completed_at = ?
                WHERE id = ?
            """).bind(status, error_message, now, scan_id).run()
        else:
            await self.db.prepare("""
                UPDATE scan_history 
                SET status = ?, points_scanned = ?, points_flagged = ?, completed_at = ?
                WHERE id = ?
            """).bind(status, points_scanned, points_flagged, now, scan_id).run()
    
    async def save_flagged_point(self, outlier: Dict[str, Any]) -> bool:
        """
        Save a flagged point if it doesn't already exist
        
        Returns:
            bool: True if point was inserted, False if already exists
        """
        # Check if already exists
        existing = await self.db.prepare(
            "SELECT id FROM flagged_points WHERE point_id = ?"
        ).bind(outlier['point_id']).first()
        
        if existing:
            return False
        
        now = int(datetime.now().timestamp())
        await self.db.prepare("""
            INSERT INTO flagged_points (
                point_id, latitude, longitude, timestamp,
                detection_reason, detection_details, confidence_score,
                previous_point_id, next_point_id,
                stay_location_lat, stay_location_lon,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """).bind(
            outlier['point_id'],
            outlier['latitude'],
            outlier['longitude'],
            outlier['timestamp'],
            outlier['detection_reason'],
            json.dumps(outlier['detection_details']),
            outlier['confidence_score'],
            outlier.get('previous_point_id', 0) or 0,
            outlier.get('next_point_id', 0) or 0,
            outlier.get('stay_location_lat', 0.0) or 0.0,
            outlier.get('stay_location_lon', 0.0) or 0.0,
            now, now
        ).run()
        
        return True
    
    async def get_dawarich_point_ids(self, flagged_ids: List[int]) -> List[int]:
        """Get Dawarich point IDs for flagged point IDs"""
        dawarich_ids = []
        for fid in flagged_ids:
            result = await self.db.prepare(
                "SELECT point_id FROM flagged_points WHERE id = ?"
            ).bind(fid).first()
            if result:
                dawarich_ids.append(result.point_id)
        return dawarich_ids
    
    async def get_points_by_ids(self, flagged_ids: List[int]) -> List[Dict[str, Any]]:
        """Get full point data for restoration"""
        points_data = []
        for fid in flagged_ids:
            result = await self.db.prepare(
                "SELECT latitude, longitude, timestamp FROM flagged_points WHERE id = ?"
            ).bind(fid).first()
            if result:
                points_data.append({
                    'latitude': result.latitude,
                    'longitude': result.longitude,
                    'timestamp': result.timestamp
                })
        return points_data
    
    async def update_points_status(
        self, 
        flagged_ids: List[int], 
        status: str
    ):
        """Update status of multiple flagged points"""
        now = int(datetime.now().timestamp())
        placeholders = ','.join(['?' for _ in flagged_ids])
        await self.db.prepare(f"""
            UPDATE flagged_points 
            SET status = ?, reviewed_at = ?
            WHERE id IN ({placeholders})
        """).bind(status, now, *flagged_ids).run()
    
    async def delete_flagged_points(self, flagged_ids: List[int]):
        """Permanently delete points from the database"""
        if not flagged_ids:
            return
        
        placeholders = ','.join(['?' for _ in flagged_ids])
        await self.db.prepare(f"""
            DELETE FROM flagged_points 
            WHERE id IN ({placeholders})
        """).bind(*flagged_ids).run()
