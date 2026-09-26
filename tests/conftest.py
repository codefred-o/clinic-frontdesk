"""Shared fixtures for isolated Vouch API tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Environment, Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        app_name="Vouch Test API",
        app_version="9.9.9",
        environment=Environment.TEST,
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/vouch_test",
        cors_origins=["https://app.vouch.test"],
    )


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client
