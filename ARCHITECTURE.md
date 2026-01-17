# Architecture Documentation

## System Overview

Dawarich Cleaner is a web application for detecting and managing GPS location outliers in Dawarich tracking data. It provides automated scanning, manual review, and bulk deletion capabilities.

## High-Level Architecture

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ HTTP
       ▼
┌─────────────────────────────────────┐
│         FastAPI Application         │
│  ┌───────────┐      ┌────────────┐ │
│  │  Routes   │◄────►│  Templates │ │
│  └─────┬─────┘      └────────────┘ │
│        │                            │
│        ▼                            │
│  ┌───────────────┐                 │
│  │   Services    │                 │
│  │ ┌───────────┐ │                 │
│  │ │ Scheduler │◄┼─────┐           │
│  │ └───────────┘ │     │ 10 min    │
│  │ ┌───────────┐ │     │ timer     │
│  │ │ Dawarich  │ │     │           │
│  │ │  Client   │◄┼─────┘           │
│  │ └───────────┘ │                 │
│  │ ┌───────────┐ │                 │
│  │ │  Outlier  │ │                 │
│  │ │ Detector  │ │                 │
│  │ └───────────┘ │                 │
│  └───────┬───────┘                 │
│          │                         │
│          ▼                         │
│  ┌───────────────┐                 │
│  │   Database    │                 │
│  └───────────────┘                 │
└──────────┬──────────────────────────┘
           │
           ▼
    ┌─────────────┐
    │   Dawarich  │
    │     API     │
    └─────────────┘
```

## Component Details

### 1. Routes (HTTP Layer)

**Location**: `app/routes/`

- **dashboard.py**: Home page, statistics
- **scan.py**: Manual scan initiation
- **review.py**: Outlier review and deletion

**Responsibilities**:
- Handle HTTP requests
- Validate input
- Render templates
- Return responses

### 2. Services (Business Logic)

**Location**: `app/services/`

#### DawarichService
- Communicates with Dawarich API
- Handles pagination (1000 points/page)
- Fetches GPS points by date range

#### OutlierDetector
- Analyzes GPS points for anomalies
- Detects:
  - Impossible speeds (>50 m/s default)
  - Large distance jumps (>50m default)
- Pure function: no I/O

#### AutoScanScheduler
- Runs every 10 minutes
- Automatically scans for new outliers
- Manages scan lifecycle
- Handles stuck/failed scans

**Key Logic**:
```python
# Uses completed_at timestamp to avoid rescanning
if last_completed:
    start = datetime.fromtimestamp(completed_at) - timedelta(minutes=5)
else:
    start = datetime.now() - timedelta(minutes=15)  # First scan
```

### 3. Database Layer

**Location**: `app/database.py`

**Tables**:
- `flagged_points`: Detected outliers
- `scan_history`: Scan execution records

**Key Operations**:
- `save_flagged_point()`: Store outlier (skip duplicates)
- `get_flagged_points()`: Retrieve for review
- `delete_flagged_points()`: Bulk deletion
- `create_scan_history()`: Track scan start
- `update_scan_history()`: Update status/results

All operations are async using aiosqlite.

### 4. Models

**Location**: `app/models.py`

Pydantic models for:
- `FlaggedPoint`: GPS outlier with metadata
- `ScanHistory`: Scan execution record
- Request/response validation

### 5. Configuration

**Location**: `app/config.py`

Settings loaded from environment:
- `DAWARICH_API_URL`: Dawarich server URL
- `DAWARICH_API_KEY`: API authentication
- `DATABASE_PATH`: SQLite database location

## Data Flow

### Manual Scan Flow
```
User Form Submit
  ↓
POST /scan (scan.py)
  ↓
DawarichService.fetch_points()
  ↓
detect_outliers()
  ↓
Database.save_flagged_point() (for each)
  ↓
Update scan_history
  ↓
Render result.html
```

### Auto Scan Flow (Every 10 minutes)
```
Timer Fires
  ↓
AutoScanScheduler._run_scan()
  ↓
Check for stuck scans
  ↓
Calculate date range from completed_at
  ↓
Validate time range (≥2 min)
  ↓
Create scan_history record
  ↓
DawarichService.fetch_points()
  ↓
detect_outliers()
  ↓
Save new outliers
  ↓
Update scan_history (completed/failed)
```

### Review & Delete Flow
```
GET /review
  ↓
Database.get_flagged_points()
  ↓
Render review.html with outliers
  ↓
User selects points
  ↓
POST /review/delete
  ↓
DawarichService.delete_points()
  ↓
Database.delete_flagged_points()
  ↓
Redirect to /review
```

## Key Design Decisions

### 1. Why Async?
- Handles concurrent API requests efficiently
- Non-blocking I/O for database and HTTP
- Better performance under load

### 2. Why SQLite?
- Simple deployment (single file)
- No separate database server needed
- Sufficient for expected workload
- Easy backups

### 3. Why 10-Minute Interval?
- Balance between freshness and API load
- Typical GPS tracking apps update every 5-10 minutes
- 5-minute overlap ensures no gaps

### 4. Why Use `completed_at` Instead of `end_date`?
- `end_date` is stored as "YYYY-MM-DD" (date-only)
- Parsing "2026-01-16" gives midnight (00:00:00)
- Subtracting 5 minutes goes to previous day (23:55:00)
- Results in repeatedly scanning same date range
- `completed_at` is actual Unix timestamp of completion
- Provides accurate continuous progression

### 5. Why Skip Duplicates?
- Same point may be detected in overlapping scans
- Prevents cluttering review interface
- Uses unique constraint on point_id

## Error Handling Strategy

### Scan Failures
- Update scan_history with error message
- Log full traceback for debugging
- Continue on next scheduled run

### API Failures
- Retry logic in DawarichService
- Timeout handling (30-second default)
- Graceful degradation

### Database Errors
- Transaction rollback where applicable
- Log errors with context
- Return HTTP 500 with user-friendly message

## Performance Considerations

### Pagination
- Fetch 1000 points per API call
- Process in batches to avoid memory issues
- Continue until empty response

### Database Indexing
- Index on point_id for duplicate checks
- Index on timestamp for date filtering

### Background Tasks
- Non-blocking scheduler using asyncio
- Cancellable tasks for clean shutdown
- Stuck scan detection (30-minute timeout)

## Testing Strategy

### Unit Tests
- Pure functions (outlier_detector)
- Database operations (mocked DB)
- Service logic (mocked external APIs)

### Integration Tests
- Full request/response cycles
- Database interactions
- Scheduler behavior

### Coverage Goals
- Minimum 80% overall
- 100% for critical paths (scheduler logic)

## Deployment

### Development
```bash
uv run uvicorn app.main:app --reload
```

### Production (Docker)
```bash
docker build -t dawarich-cleaner .
docker run -p 8000:8000 -v ./data:/app/data dawarich-cleaner
```

### Environment Variables
```
DAWARICH_API_URL=http://dawarich.example.com
DAWARICH_API_KEY=your-api-key
DATABASE_PATH=/app/data/dawarich_cleaner.db
```

## Future Enhancements

### Potential Features
- [ ] Configurable scan interval
- [ ] Multiple detection strategies
- [ ] Export outliers to GPX/KML
- [ ] REST API for external integrations
- [ ] Real-time scan progress updates
- [ ] User authentication
- [ ] Multi-user support

### Technical Improvements
- [ ] PostgreSQL support for multi-user
- [ ] Celery for distributed background tasks
- [ ] Redis for caching
- [ ] Prometheus metrics
- [ ] Health check endpoint improvements
