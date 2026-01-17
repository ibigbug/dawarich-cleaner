-- Dawarich Cleaner D1 Database Schema

-- Table to store flagged points for review
CREATE TABLE IF NOT EXISTS flagged_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Point identification
    point_id INTEGER NOT NULL,
    
    -- Point data from Dawarich
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    timestamp INTEGER NOT NULL, -- Unix timestamp
    accuracy REAL,
    altitude REAL,
    speed REAL,
    
    -- Detection information
    detection_reason TEXT NOT NULL, -- 'jump_back', 'unrealistic_speed', 'oscillating'
    detection_details TEXT, -- JSON with additional context
    confidence_score REAL, -- 0-1 score indicating confidence in detection
    
    -- Related context
    previous_point_id INTEGER,
    next_point_id INTEGER,
    stay_location_lat REAL, -- For jump_back detections
    stay_location_lon REAL,
    
    -- Review status
    status TEXT DEFAULT 'pending', -- 'pending', 'deleted', 'restored', 'ignored'
    reviewed_at INTEGER, -- Unix timestamp
    
    -- Metadata
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    
    -- Index for efficient queries
    UNIQUE(point_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_flagged_points_status ON flagged_points(status);
CREATE INDEX IF NOT EXISTS idx_flagged_points_timestamp ON flagged_points(timestamp);
CREATE INDEX IF NOT EXISTS idx_flagged_points_detection_reason ON flagged_points(detection_reason);
CREATE INDEX IF NOT EXISTS idx_flagged_points_created_at ON flagged_points(created_at);

-- Table to track scan history
CREATE TABLE IF NOT EXISTS scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    start_date TEXT NOT NULL, -- ISO date string
    end_date TEXT NOT NULL,
    
    points_scanned INTEGER DEFAULT 0,
    points_flagged INTEGER DEFAULT 0,
    
    scan_type TEXT NOT NULL, -- 'manual', 'cron'
    status TEXT NOT NULL, -- 'running', 'completed', 'failed'
    error_message TEXT,
    
    started_at INTEGER NOT NULL,
    completed_at INTEGER,
    
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scan_history_started_at ON scan_history(started_at DESC);
