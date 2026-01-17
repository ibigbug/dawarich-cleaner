# GitHub Copilot Instructions for Dawarich Cleaner

## Project Context
You're working on a FastAPI web application that detects GPS outliers in location tracking data from Dawarich. The app scans GPS points, identifies anomalies (impossible speeds, distance jumps), and allows manual review/deletion.

## Key Technical Details

### Tech Stack
- **Backend**: FastAPI (Python 3.12+)
- **Frontend**: Jinja2 templates, vanilla JavaScript
- **Database**: SQLite with aiosqlite (async)
- **HTTP Client**: httpx (async)
- **Testing**: pytest, pytest-asyncio
- **Package Management**: uv

### Critical Implementation Details

#### Scheduler Time Handling (IMPORTANT!)
```python
# ✅ CORRECT - Use completed_at timestamp
if completed_at:
    start_date = datetime.fromtimestamp(completed_at) - timedelta(minutes=5)

# ❌ WRONG - Don't use end_date string (parses to midnight)
end_date_str = last_completed["end_date"]  # "2026-01-16"
start_date = datetime.strptime(end_date_str, "%Y-%m-%d")  # 2026-01-16 00:00:00
```

The scheduler must use `completed_at` timestamp to avoid repeatedly scanning the same date range.

#### Async Patterns
```python
# Database operations are always async
async def some_route(request: Request):
    db: Database = request.app.state.db
    result = await db.get_something()
```

#### Dependency Injection
```python
# Get database from app state
@router.get("/route")
async def handler(request: Request):
    db: Database = request.app.state.db
    settings = get_settings()
```

### Common Tasks

#### Adding a New Route
1. Create route handler in `app/routes/`
2. Add Pydantic models if needed in `app/models.py`
3. Create Jinja2 template in `templates/`
4. Include router in `app/main.py`
5. Add tests in `tests/test_routes.py`

#### Adding a Database Method
1. Add method to `Database` class in `app/database.py`
2. Make it async: `async def method_name(self, ...)`
3. Use `async with self.conn.execute(...)` for queries
4. Add test in `tests/test_database.py`

#### Modifying the Scheduler
1. Edit `app/services/scheduler.py`
2. **Always** add tests in `tests/test_scheduler.py`
3. Test time-related logic carefully
4. Use mocks for external services

### Testing Conventions
```python
# Mock database
mock_db = MagicMock()
mock_db.some_method = AsyncMock(return_value=data)

# Mock external services
with patch("app.services.scheduler.DawarichService") as mock_service:
    mock_service.return_value.fetch_points = AsyncMock(return_value=[])
    # ... test code

# Run tests
# uv run pytest
# uv run pytest -v tests/test_scheduler.py
```

### Code Style Preferences
- Use type hints: `def func(x: int) -> str:`
- Use async/await for I/O operations
- Log with emojis for visibility: `logger.info("✅ Success")`
- Use descriptive names: `points_scanned` not `pts_cnt`
- Handle errors explicitly with try/except
- Update scan status on failures

### File Structure Guide
```
app/
  ├── main.py              # App initialization, startup/shutdown
  ├── config.py            # Settings (env vars)
  ├── database.py          # All database operations
  ├── models.py            # Pydantic models
  ├── routes/              # HTTP endpoints (organized by feature)
  │   ├── dashboard.py     # Home/stats
  │   ├── scan.py          # Scan operations
  │   └── review.py        # Review/delete outliers
  └── services/            # Business logic (no HTTP)
      ├── dawarich.py      # API client
      ├── outlier_detector.py  # Detection algorithms
      └── scheduler.py     # Background tasks
```

## When Suggesting Changes
1. **Consider async context** - Most operations are async
2. **Check existing patterns** - Match coding style in the file
3. **Think about tests** - Suggest test updates for logic changes
4. **Handle errors** - Add appropriate error handling
5. **Update scan history** - Mark scans as completed/failed
6. **Log appropriately** - Use structured logging with emojis
