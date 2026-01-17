#!/usr/bin/env python3
"""
WSGI/ASGI entry point for running the FastAPI application
"""
import uvicorn
import os
from pathlib import Path
from dotenv import load_dotenv

if __name__ == "__main__":
    # Load environment from .env file if it exists
    env_file = os.environ.get("ENV_FILE", ".env")
    env_path = Path(env_file)

    if env_path.exists():
        load_dotenv(env_path, override=False)
        print(f"✓ Loaded environment from: {env_file}")
    else:
        print(f"⚠ Environment file not found: {env_file}")
        print("  Using environment variables from system")

    # Run with uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 8000)),
        reload=True,
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )
