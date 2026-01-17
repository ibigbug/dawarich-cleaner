"""
Minimal entry point for Cloudflare Worker
All heavy imports deferred to request time
"""

import os

# Global app instance (created on first request)
_app = None


def get_app():
    """Lazy create FastAPI app on first request"""
    global _app
    if _app is None:
        from fastapi import FastAPI

        is_dev = os.environ.get("ENVIRONMENT", "development") == "development"
        _app = FastAPI(
            title="Dawarich Cleaner",
            version="1.0.0",
            debug=is_dev,
            docs_url="/docs" if is_dev else None,
            redoc_url=None,
        )

        # Import and setup routes
        from worker_routes import setup_routes

        setup_routes(_app)

    return _app


# Cloudflare Workers handlers
async def on_fetch(request, env):
    """Fetch handler"""
    import asgi

    app = get_app()
    return await asgi.fetch(app, request, env)


async def scheduled(event, env, ctx):
    """Cron handler"""
    from worker_routes import handle_cron

    await handle_cron(event, env, ctx)
