"""Configuration settings"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # Dawarich API
    dawarich_api_url: str
    dawarich_api_key: str

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

    class Config:
        # Respect ENV_FILE environment variable, default to .env
        env_file = os.getenv("ENV_FILE", ".env")
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields for forward compatibility


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
