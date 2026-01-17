"""Review and action routes"""

import logging
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..config import get_settings
from ..database import Database
from ..services import DawarichService

router = APIRouter()
template_dir = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))
logger = logging.getLogger(__name__)


@router.get("/review", response_class=HTMLResponse)
async def review(
    request: Request,
    status: str = "pending",
    min_confidence: float = 0.0,
):
    """Display flagged points for review"""
    settings = get_settings()
    db: Database = request.app.state.db

    # Get stats for tab counts
    stats = await db.get_stats()

    # Get filtered points
    flagged_points = await db.get_flagged_points(
        status=status if status else None,
        min_confidence=min_confidence,
    )

    return templates.TemplateResponse(
        "review.html",
        {
            "request": request,
            "flagged_points": flagged_points,
            "stats": stats,
            "status_filter": status,
            "min_confidence": min_confidence,
            "dawarich_api_url": settings.dawarich_api_url,
        },
    )


@router.post("/action/{action}", response_class=HTMLResponse)
async def action(request: Request, action: str, point_ids: list[str] = Form(...)):
    """Perform bulk action on flagged points"""
    settings = get_settings()
    db: Database = request.app.state.db

    try:
        # These are database IDs, not Dawarich point_ids
        db_ids = [int(id.strip()) for id in point_ids if id.strip()]
        if not db_ids:
            raise ValueError("No point IDs provided")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid point IDs: {str(e)}") from e

    # Get the actual Dawarich point_ids from database IDs
    flagged_points = await db.get_flagged_points(status="all")
    id_map = {p["id"]: p["point_id"] for p in flagged_points}
    dawarich_point_ids = [id_map[db_id] for db_id in db_ids if db_id in id_map]

    if not dawarich_point_ids:
        raise HTTPException(status_code=400, detail="No valid points found")

    dawarich = DawarichService(settings.dawarich_api_url, settings.dawarich_api_key)
    success = True
    message = ""

    try:
        if action == "delete":
            logger.info(f"Deleting {len(dawarich_point_ids)} points from Dawarich")
            await dawarich.delete_points(dawarich_point_ids)
            await db.mark_as_deleted(dawarich_point_ids)
            message = f"Successfully deleted {len(dawarich_point_ids)} points from Dawarich"

        elif action == "restore":
            logger.info(f"Restoring {len(dawarich_point_ids)} points by re-importing to Dawarich")

            # Get point data from flagged_points
            points_to_restore = [
                {
                    "latitude": p["latitude"],
                    "longitude": p["longitude"],
                    "timestamp": p["timestamp"],
                }
                for p in flagged_points
                if p["point_id"] in dawarich_point_ids
            ]

            if not points_to_restore:
                raise HTTPException(status_code=400, detail="No point data found to restore")

            # Re-import points to Dawarich via POST API (creates new points with new IDs)
            await dawarich.reimport_points(points_to_restore)

            # Remove old flagged records since restored points have new IDs now
            # They would need to be re-scanned if they're still outliers
            await db.remove_flagged_points(dawarich_point_ids)

            message = f"Successfully restored {len(dawarich_point_ids)} points (re-imported to Dawarich with new IDs - removed from flagged list)"

        elif action == "ignore":
            logger.info(f"Ignoring {len(dawarich_point_ids)} points")
            await db.mark_as_ignored(dawarich_point_ids)
            message = f"Successfully ignored {len(dawarich_point_ids)} points (kept in Dawarich, marked as reviewed)"

        elif action == "remove":
            logger.info(f"Removing {len(dawarich_point_ids)} points from database")
            await db.remove_flagged_points(dawarich_point_ids)
            message = f"Successfully removed {len(dawarich_point_ids)} points from database"

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    except Exception as e:
        logger.error(f"Error performing action {action}: {e}")
        message = f"Error: {str(e)}"
        success = False

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "success": success,
            "message": message,
            "redirect_url": "/review",
            "details": {"action": action, "points_affected": len(dawarich_point_ids)},
        },
    )
