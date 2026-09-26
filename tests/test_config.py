"""Configuration validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Environment, Settings


def test_settings_use_vouch_defaults_without_env_file() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "Vouch API"
    assert settings.environment == Environment.DEVELOPMENT
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_cors_origins_are_normalized() -> None:
    settings = Settings(_env_file=None, cors_origins=["https://app.vouch.test/"])

    assert settings.cors_origin_values == ["https://app.vouch.test"]


def test_production_rejects_debug_mode() -> None:
    with pytest.raises(ValidationError, match="debug must be disabled in production"):
        Settings(_env_file=None, environment=Environment.PRODUCTION, debug=True)


def test_pool_size_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_pool_size=0)
