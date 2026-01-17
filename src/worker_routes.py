"""
Route handlers - all imports deferred
"""


def setup_routes(app):
    """Setup all routes with deferred imports"""
    from fastapi import Form, Request, HTTPException
    from fastapi.responses import HTMLResponse, Response, JSONResponse
    from datetime import datetime, timedelta
    from typing import List, Optional
    import traceback
    import logging
    import os

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)
    is_dev = os.environ.get("ENVIRONMENT", "development") == "development"

    # Lazy loaders
    def get_templates():
        from fastapi.templating import Jinja2Templates
        import pathlib

        template_dir = pathlib.Path(__file__).parent / "templates"
        return Jinja2Templates(directory=str(template_dir))

    def get_db(env):
        from database import Database

        return Database(env.DB)

    def get_client(env):
        from dawarich_client import DawarichClient

        return DawarichClient(env.DAWARICH_API_URL, env.DAWARICH_API_KEY)

    def detect_outliers_fn(points, max_speed_kmh=150, max_distance_km=0.5):
        from outlier_detector import detect_outliers

        return detect_outliers(points, max_speed_kmh, max_distance_km)

    def validate_environment(env) -> Optional[str]:
        if not hasattr(env, "DB"):
            return "Database (DB) binding is not configured"
        if not hasattr(env, "DAWARICH_API_URL") or not env.DAWARICH_API_URL:
            return "DAWARICH_API_URL environment variable is not set"
        if not hasattr(env, "DAWARICH_API_KEY") or not env.DAWARICH_API_KEY:
            return "DAWARICH_API_KEY environment variable is not set"
        return None

    # Exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        error_details = {
            "error": str(exc),
            "type": type(exc).__name__,
            "path": request.url.path,
        }
        if is_dev:
            error_details["traceback"] = traceback.format_exc()

        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            templates = get_templates()
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

    # Health check
    @app.get("/health")
    async def health_check():
        return JSONResponse(
            content={
                "status": "healthy",
                "service": "dawarich-cleaner",
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat(),
            },
            status_code=200,
        )

    # Favicon
    @app.get("/static/favicon.svg")
    async def favicon():
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

    # Dashboard
    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        env = request.scope["env"]
        error = validate_environment(env)
        if error:
            logger.error(f"Environment validation failed: {error}")
            raise HTTPException(status_code=500, detail=error)

        db = get_db(env)
        stats = await db.get_stats()
        return get_templates().TemplateResponse(
            "dashboard.html", {"request": request, "stats": stats}
        )

    # Scan
    @app.post("/scan", response_class=HTMLResponse)
    async def scan(
        request: Request,
        start_date: str = Form(...),
        end_date: str = Form(...),
        timezone: str = Form("UTC"),
        max_speed: float = Form(200),
        jump_radius: float = Form(5),
    ):
        try:
            env = request.scope["env"]
            error = validate_environment(env)
            if error:
                raise Exception(error)

            # Validate inputs
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

            logger.info(f"Starting scan: {start_date} to {end_date}")

            db = get_db(env)
            scan_id = await db.create_scan_history(start_date, end_date, "manual")

            client = get_client(env)
            points = await client.fetch_points(start_date, end_date, timezone)

            if not points:
                await db.update_scan_history(scan_id, "completed", 0, 0)
                return get_templates().TemplateResponse(
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

            logger.info(f"Analyzing {len(points)} points for outliers")
            outliers = detect_outliers_fn(
                points, max_speed_kmh=max_speed, max_distance_km=jump_radius
            )
            logger.info(f"Detected {len(outliers)} potential outliers")

            new_count = 0
            for outlier in outliers:
                if await db.save_flagged_point(outlier):
                    new_count += 1

            await db.update_scan_history(scan_id, "completed", len(points), new_count)
            logger.info(
                f"Scan completed: {len(points)} points scanned, {new_count} new outliers flagged"
            )

            message = f"Scanned {len(points)} points and flagged {new_count} outliers"
            return get_templates().TemplateResponse(
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
            logger.error(f"Scan failed: {str(e)}", exc_info=True)
            return get_templates().TemplateResponse(
                "result.html",
                {
                    "request": request,
                    "success": False,
                    "message": f"Scan failed: {str(e)}",
                    "redirect_url": "/",
                },
            )

    # Review
    @app.get("/review", response_class=HTMLResponse)
    async def review(
        request: Request, status: str = "pending", min_confidence: float = 0.5
    ):
        env = request.scope["env"]
        db = get_db(env)
        flagged_points = await db.get_points_by_status(
            status=status, min_confidence=min_confidence
        )
        stats = await db.get_stats()
        return get_templates().TemplateResponse(
            "review.html",
            {
                "request": request,
                "flagged_points": flagged_points,
                "stats": stats,
                "min_confidence": min_confidence,
                "status_filter": status,
            },
        )

    # Actions
    @app.post("/action/{action}", response_class=HTMLResponse)
    async def handle_action(
        request: Request, action: str, point_ids: List[int] = Form(...)
    ):
        try:
            env = request.scope["env"]
            error = validate_environment(env)
            if error:
                raise Exception(error)

            valid_actions = ["delete", "ignore", "restore", "remove"]
            if action not in valid_actions:
                raise ValueError(f"Invalid action '{action}'")

            db = get_db(env)

            if not point_ids:
                logger.warning("No points selected for action")
                return get_templates().TemplateResponse(
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
                dawarich_point_ids = await db.get_dawarich_point_ids(point_ids)
                if dawarich_point_ids:
                    client = get_client(env)
                    await client.delete_points(dawarich_point_ids)
                await db.update_points_status(point_ids, "deleted")
                message = f"Successfully deleted {len(point_ids)} points from Dawarich"

            elif action == "ignore":
                await db.update_points_status(point_ids, "ignored")
                message = f"Marked {len(point_ids)} points as ignored"

            elif action == "restore":
                points_data = await db.get_points_by_ids(point_ids)
                if points_data:
                    client = get_client(env)
                    await client.restore_points(points_data)
                await db.update_points_status(point_ids, "pending")
                message = f"Successfully restored {len(point_ids)} points to Dawarich"

            elif action == "remove":
                await db.delete_flagged_points(point_ids)
                message = f"Permanently removed {len(point_ids)} points from database"

            logger.info(f"Action '{action}' completed: {message}")
            return get_templates().TemplateResponse(
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
            return get_templates().TemplateResponse(
                "result.html",
                {
                    "request": request,
                    "success": False,
                    "message": f"Action failed: {str(e)}",
                    "redirect_url": "/review",
                },
            )


async def handle_cron(event, env, ctx):
    """Cron job handler"""
    from datetime import datetime, timedelta
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"Cron job triggered at {event.cron}")

    try:
        from database import Database
        from dawarich_client import DawarichClient
        from outlier_detector import detect_outliers

        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        logger.info(f"Scanning from {start_date_str} to {end_date_str}")

        db = Database(env.DB)
        scan_id = await db.create_scan_history(start_date_str, end_date_str, "cron")

        client = DawarichClient(env.DAWARICH_API_URL, env.DAWARICH_API_KEY)
        points = await client.fetch_points(start_date_str, end_date_str)

        if not points:
            logger.info("No points found in date range")
            await db.update_scan_history(scan_id, "completed", 0, 0)
            return

        logger.info(f"Analyzing {len(points)} points for outliers")
        outliers = detect_outliers(points)

        new_count = 0
        for outlier in outliers:
            if await db.save_flagged_point(outlier):
                new_count += 1

        await db.update_scan_history(scan_id, "completed", len(points), new_count)
        logger.info(
            f"Cron scan completed: {len(points)} points scanned, {new_count} new outliers flagged"
        )

    except Exception as e:
        logger.error(f"Error during cron execution: {str(e)}", exc_info=True)
        try:
            await db.update_scan_history(scan_id, "failed", error_message=str(e))
        except:
            pass
        raise
