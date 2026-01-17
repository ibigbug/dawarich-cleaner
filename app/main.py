"""Main FastAPI application"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import Database
from .routes import dashboard_router, review_router, scan_router
from .services.scheduler import AutoScanScheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize application on startup"""
    settings = get_settings()

    # Create data directory for SQLite if needed
    if settings.is_sqlite:
        # Extract path from sqlite URL (e.g., sqlite+aiosqlite:///./data/db.db)
        db_path = settings.database_url.split("///")[-1]
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    # Initialize database
    db = Database(settings.database_url)
    await db.init_db()
    app.state.db = db
    logger.info(f"Database initialized: {settings.database_url}")

    # Start auto-scan scheduler
    scheduler = AutoScanScheduler(db)
    await scheduler.start()
    app.state.scheduler = scheduler

    yield

    # Cleanup
    await scheduler.stop()
    await db.close()
    logger.info("Database connection closed")


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    # Include routers
    app.include_router(dashboard_router)
    app.include_router(scan_router)
    app.include_router(review_router)

    # Mount static files
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Favicon redirect
    @app.get("/favicon.ico")
    async def favicon_ico():
        return RedirectResponse(url="/static/favicon.svg", status_code=301)

    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        scheduler_running = hasattr(app.state, "scheduler") and app.state.scheduler._running
        return {
            "status": "healthy",
            "service": settings.app_name,
            "version": settings.app_version,
            "auto_scan_enabled": scheduler_running,
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
