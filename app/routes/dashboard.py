"""Dashboard routes"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from ..database import Database

router = APIRouter()
template_dir = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Display dashboard with statistics"""
    db: Database = request.app.state.db
    stats = await db.get_stats()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "stats": stats},
    )
