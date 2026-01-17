"""Tests for configuration"""

from app.config import Settings, get_settings


def test_settings_defaults():
    """Test default settings values"""
    settings = Settings(dawarich_api_url="http://localhost:3000", dawarich_api_key="test")
    assert settings.app_name == "Dawarich Cleaner"
    assert settings.app_version == "2.0.0"
    assert settings.database_url == "sqlite+aiosqlite:///./data/dawarich-cleaner.db"
    # Debug value depends on env, skip checking default


def test_settings_is_sqlite():
    """Test is_sqlite property"""
    # SQLite URL
    settings = Settings(
        dawarich_api_url="http://test",
        dawarich_api_key="test",
        database_url="sqlite+aiosqlite:///./data/test.db",
    )
    assert settings.is_sqlite is True

    # PostgreSQL URL
    settings = Settings(
        dawarich_api_url="http://test",
        dawarich_api_key="test",
        database_url="postgresql+asyncpg://user:pass@localhost/db",
    )
    assert settings.is_sqlite is False


def test_settings_from_env(monkeypatch):
    """Test settings loaded from environment"""
    monkeypatch.setenv("DAWARICH_API_URL", "https://example.com")
    monkeypatch.setenv("DAWARICH_API_KEY", "secret123")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("DEBUG", "true")

    # Clear cache
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.dawarich_api_url == "https://example.com"
    assert settings.dawarich_api_key == "secret123"
    assert settings.database_url == "postgresql://test"
    assert settings.debug is True


def test_get_settings_cached():
    """Test that get_settings returns cached instance"""
    get_settings.cache_clear()
    settings1 = get_settings()
    settings2 = get_settings()
    assert settings1 is settings2
