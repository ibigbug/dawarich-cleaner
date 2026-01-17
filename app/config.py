"""Configuration settings"""

import os
from functools import lru_cache

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    model_config = ConfigDict(
        env_file=os.getenv("ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Dawarich API
    dawarich_api_url: str = "http://localhost:3000"
    dawarich_api_key: str = "test_key"

    # Database - supports both SQLite and PostgreSQL
    database_url: str = "sqlite+aiosqlite:///./data/dawarich-cleaner.db"

    # Application
    app_name: str = "Dawarich Cleaner"
    app_version: str = "2.0.0"
    debug: bool = False

    @property
    def is_sqlite(self) -> bool:
        """Check if database is SQLite"""
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
