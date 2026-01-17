"""
Dawarich Cleaner - Python Cloudflare Worker with Cron Job
FastAPI-based web application for detecting and cleaning GPS outliers
"""

from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
from typing import List, Optional
import os
import traceback
import logging

from dawarich_client import DawarichClient
from outlier_detector import detect_outliers
from database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
is_dev = os.environ.get("ENVIRONMENT", "development") == "development"
app = FastAPI(
    title="Dawarich Cleaner",
    version="1.0.0",
    debug=is_dev,
    docs_url="/docs" if is_dev else None,  # Disable docs in production
    redoc_url=None,
)

# Initialize Jinja2 templates
import pathlib

template_dir = pathlib.Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))


# Configuration validation
def validate_environment(env) -> Optional[str]:
    """Validate required environment variables"""
    if not hasattr(env, "DB"):
        return "Database (DB) binding is not configured"
    if not hasattr(env, "DAWARICH_API_URL") or not env.DAWARICH_API_URL:
        return "DAWARICH_API_URL environment variable is not set"
    if not hasattr(env, "DAWARICH_API_KEY") or not env.DAWARICH_API_KEY:
        return "DAWARICH_API_KEY environment variable is not set"
    return None


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all uncaught exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    error_details = {
        "error": str(exc),
        "type": type(exc).__name__,
        "path": request.url.path,
    }

    if is_dev:
        error_details["traceback"] = traceback.format_exc()

    # Return JSON for API-like requests, HTML for browser requests
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "traceback": traceback.format_exc() if is_dev else None,
            },
            status_code=500,
        )

    return JSONResponse(content=error_details, status_code=500)


# Cloudflare Workers handler - bridges to FastAPI
async def on_fetch(request, env):
    """
    Cloudflare Workers fetch handler
    Bridges requests to FastAPI app
    """
    import asgi

    try:
        return await asgi.fetch(app, request, env)
    except Exception as e:
        # Return detailed error for debugging in dev
        if is_dev:
            import traceback
            from js import Response

            error_detail = {
                "error": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc(),
            }
            return Response.json(error_detail, {"status": 500})
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return JSONResponse(
        content={
            "status": "healthy",
            "service": "dawarich-cleaner",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
        },
        status_code=200,
    )


@app.get("/static/favicon.svg")
async def favicon():
    """Serve favicon - embedded SVG content"""
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <circle cx="50" cy="50" r="48" fill="#2563eb" stroke="#1e40af" stroke-width="2"/>
    <path d="M50 25 C42 25 35 32 35 40 C35 52 50 65 50 65 C50 65 65 52 65 40 C65 32 58 25 50 25 Z" fill="#ffffff" opacity="0.9"/>
    <circle cx="50" cy="40" r="5" fill="#2563eb"/>
    <path d="M30 70 L35 55 L40 55 L35 70 Z" fill="#fbbf24" opacity="0.9"/>
    <rect x="33" y="52" width="4" height="20" fill="#78716c" opacity="0.9"/>
    <circle cx="60" cy="70" r="2" fill="#fbbf24"/>
    <circle cx="68" cy="75" r="1.5" fill="#fbbf24"/>
    <circle cx="55" cy="78" r="1.5" fill="#fbbf24"/>
</svg>"""
    return Response(content=svg_content, media_type="image/svg+xml")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    env = request.scope["env"]

    # Validate environment
    error = validate_environment(env)
    if error:
        logger.error(f"Environment validation failed: {error}")
        raise HTTPException(status_code=500, detail=error)

    db = Database(env.DB)
    stats = await db.get_stats()

    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "stats": stats}
    )


@app.post("/scan", response_class=HTMLResponse)
async def scan(
    request: Request,
    start_date: str = Form(...),
    end_date: str = Form(...),
    timezone: str = Form("UTC"),
    max_speed: float = Form(200),
    jump_radius: float = Form(5),
):
    """Handle scan request with input validation"""
    try:
        env = request.scope["env"]

        # Validate environment
        error = validate_environment(env)
        if error:
            logger.error(f"Environment validation failed: {error}")
            raise Exception(error)

        # Validate input parameters
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            if end_dt < start_dt:
                raise ValueError("End date must be after start date")

            if (end_dt - start_dt).days > 365:
                raise ValueError("Date range cannot exceed 365 days")

            if max_speed < 1 or max_speed > 1000:
                raise ValueError("Max speed must be between 1 and 1000 km/h")

            if jump_radius < 0.1 or jump_radius > 100:
                raise ValueError("Jump radius must be between 0.1 and 100 km")
        except ValueError as e:
            raise Exception(f"Invalid input: {str(e)}")

        logger.info(
            f"Starting scan: {start_date} to {end_date}, timezone={timezone}, max_speed={max_speed}, jump_radius={jump_radius}"
        )

        db = Database(env.DB)

        # Create scan history
        scan_id = await db.create_scan_history(start_date, end_date, "manual")

        # Fetch points from Dawarich
        client = DawarichClient(env.DAWARICH_API_URL, env.DAWARICH_API_KEY)
        points = await client.fetch_points(start_date, end_date, timezone)

        if not points:
            await db.update_scan_history(scan_id, "completed", 0, 0)
            return templates.TemplateResponse(
                "result.html",
                {
                    "request": request,
                    "success": True,
                    "message": "No points found in the date range",
                    "redirect_url": "/",
                    "details": {
                        "start_date": start_date,
                        "end_date": end_date,
                        "points_scanned": 0,
                        "points_flagged": 0,
                    },
                },
            )

        # Detect outliers
        logger.info(f"Analyzing {len(points)} points for outliers")
        outliers = detect_outliers(
            points, max_speed_kmh=max_speed, max_distance_km=jump_radius
        )
        logger.info(f"Detected {len(outliers)} potential outliers")

        # Store flagged points
        new_count = 0
        for outlier in outliers:
            if await db.save_flagged_point(outlier):
                new_count += 1

        # Update scan history
        await db.update_scan_history(scan_id, "completed", len(points), new_count)

        logger.info(
            f"Scan completed: {len(points)} points scanned, {new_count} new outliers flagged"
        )
        message = f"Scanned {len(points)} points and flagged {new_count} outliers"
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "success": True,
                "message": message,
                "redirect_url": "/review",
                "details": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "points_scanned": len(points),
                    "points_flagged": new_count,
                },
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "success": False,
                "message": f"Scan failed: {str(e)}",
                "redirect_url": "/",
            },
        )


@app.get("/review", response_class=HTMLResponse)
async def review(
    request: Request, status: str = "pending", min_confidence: float = 0.5
):
    """Review flagged points page with status filter"""
    env = request.scope["env"]
    db = Database(env.DB)

    # Get points filtered by status
    flagged_points = await db.get_points_by_status(
        status=status, min_confidence=min_confidence
    )
    stats = await db.get_stats()

    return templates.TemplateResponse(
        "review.html",
        {
            "request": request,
            "flagged_points": flagged_points,
            "stats": stats,
            "min_confidence": min_confidence,
            "status_filter": status,
        },
    )


@app.post("/action/{action}", response_class=HTMLResponse)
async def handle_action(
    request: Request, action: str, point_ids: List[int] = Form(...)
):
    """Handle batch actions on flagged points"""
    try:
        env = request.scope["env"]

        # Validate environment
        error = validate_environment(env)
        if error:
            logger.error(f"Environment validation failed: {error}")
            raise Exception(error)

        # Validate action
        valid_actions = ["delete", "ignore", "restore", "remove"]
        if action not in valid_actions:
            raise ValueError(
                f"Invalid action '{action}'. Must be one of: {', '.join(valid_actions)}"
            )

        db = Database(env.DB)

        if not point_ids:
            logger.warning("No points selected for action")
            return templates.TemplateResponse(
                "result.html",
                {
                    "request": request,
                    "success": False,
                    "message": "No points selected",
                    "redirect_url": "/review",
                },
            )

        logger.info(f"Performing action '{action}' on {len(point_ids)} points")

        if action == "delete":
            # Get Dawarich point IDs
            dawarich_point_ids = await db.get_dawarich_point_ids(point_ids)

            # Delete from Dawarich
            if dawarich_point_ids:
                client = DawarichClient(env.DAWARICH_API_URL, env.DAWARICH_API_KEY)
                await client.delete_points(dawarich_point_ids)

            # Update status in database
            await db.update_points_status(point_ids, "deleted")
            message = f"Successfully deleted {len(point_ids)} points from Dawarich"

        elif action == "ignore":
            # Mark as ignored
            await db.update_points_status(point_ids, "ignored")
            message = f"Marked {len(point_ids)} points as ignored"

        elif action == "restore":
            # Get point details from database
            points_data = await db.get_points_by_ids(point_ids)

            if points_data:
                # Restore to Dawarich
                client = DawarichClient(env.DAWARICH_API_URL, env.DAWARICH_API_KEY)
                await client.restore_points(points_data)

            # Update status back to pending (in case user changes mind)
            await db.update_points_status(point_ids, "pending")
            message = f"Successfully restored {len(point_ids)} points to Dawarich"

        elif action == "remove":
            # Permanently delete from database
            await db.delete_flagged_points(point_ids)
            message = f"Permanently removed {len(point_ids)} points from database"

        logger.info(f"Action '{action}' completed successfully")
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "success": True,
                "message": message,
                "redirect_url": "/review",
            },
        )

    except Exception as e:
        logger.error(f"Action '{action}' failed: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "success": False,
                "message": f"Action failed: {str(e)}",
                "redirect_url": "/review",
            },
        )


# Cron handler (kept separate from FastAPI routing)
async def scheduled(event, env, ctx):
    """
    Cron job handler - runs on the schedule defined in wrangler.toml

    Args:
        event: Contains cron schedule information
        env: Environment bindings (KV, D1, secrets, etc.)
        ctx: Context for waitUntil and passThroughOnException
    """
    logger.info(f"Cron job triggered at {event.cron}")

    try:
        # Validate environment
        error = validate_environment(env)
        if error:
            logger.error(f"Environment validation failed: {error}")
            raise Exception(error)

        # Scan last 7 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        logger.info(f"Scanning from {start_date_str} to {end_date_str}")

        db = Database(env.DB)

        # Create scan history
        scan_id = await db.create_scan_history(start_date_str, end_date_str, "cron")

        # Fetch and process points
        client = DawarichClient(env.DAWARICH_API_URL, env.DAWARICH_API_KEY)
        points = await client.fetch_points(start_date_str, end_date_str)

        if not points:
            logger.info("No points found in date range")
            await db.update_scan_history(scan_id, "completed", 0, 0)
            return

        # Detect outliers
        logger.info(f"Analyzing {len(points)} points for outliers")
        outliers = detect_outliers(points)

        # Store new flagged points
        new_count = 0
        for outlier in outliers:
            if await db.save_flagged_point(outlier):
                new_count += 1

        # Update scan history
        await db.update_scan_history(scan_id, "completed", len(points), new_count)

        logger.info(
            f"Cron scan completed: {len(points)} points scanned, {new_count} new outliers flagged"
        )

    except Exception as e:
        logger.error(f"Error during cron execution: {str(e)}", exc_info=True)
        # Try to update scan history
        try:
            await db.update_scan_history(scan_id, "failed", error_message=str(e))
        except:
            pass
        raise
