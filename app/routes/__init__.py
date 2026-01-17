"""Routes package"""

from .dashboard import router as dashboard_router
from .review import router as review_router
from .scan import router as scan_router

__all__ = ["dashboard_router", "scan_router", "review_router"]
