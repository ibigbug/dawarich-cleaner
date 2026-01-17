"""Scan routes"""

import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..config import get_settings
from ..database import Database
from ..services import DawarichService, detect_outliers

router = APIRouter()
template_dir = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))
logger = logging.getLogger(__name__)


@router.post("/scan", response_class=HTMLResponse)
async def scan(
    request: Request,
    start_date: str = Form(...),
    end_date: str = Form(...),
    timezone: str = Form("UTC"),
    max_speed: float = Form(30),
    jump_radius: int = Form(500),
):
    """Run outlier detection scan"""
    settings = get_settings()
    db: Database = request.app.state.db

    # Validate inputs
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if end_dt < start_dt:
            raise ValueError("End date must be after start date")
        if (end_dt - start_dt).days > 365:
            raise ValueError("Date range cannot exceed 365 days")
        if max_speed < 1 or max_speed > 280:
            raise ValueError("Max speed must be between 1 and 280 m/s")
        if jump_radius < 5 or jump_radius > 10000:
            raise ValueError("Jump radius must be between 5 and 10000 meters")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}") from e

    logger.info(f"Starting scan: {start_date} to {end_date}")

    scan_id = await db.create_scan_history(start_date, end_date, "manual")

    dawarich = DawarichService(settings.dawarich_api_url, settings.dawarich_api_key)
    points = await dawarich.fetch_points(start_date, end_date, timezone)

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

    logger.info(f"Analyzing {len(points)} points for outliers")
    outliers = detect_outliers(points, max_speed_ms=max_speed, max_distance_m=jump_radius)
    logger.info(f"Detected {len(outliers)} potential outliers")

    new_count = 0
    for outlier in outliers:
        if await db.save_flagged_point(outlier):
            new_count += 1

    await db.update_scan_history(scan_id, "completed", len(points), new_count)
    logger.info(f"Scan completed: {len(points)} points scanned, {new_count} new outliers flagged")

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
