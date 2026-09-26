"""Application factory and HTTP boundary tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Environment, Settings
from app.main import create_app


def test_application_exposes_vouch_metadata(settings: Settings) -> None:
    application = create_app(settings)

    assert application.title == "Vouch Test API"
    assert application.version == "9.9.9"


def test_liveness_returns_branded_service_status(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Vouch Test API",
        "version": "9.9.9",
    }
    assert response.headers["X-Request-ID"]


def test_cors_allows_only_configured_web_origin(client: TestClient) -> None:
    response = client.options(
        "/api/v1/health/live",
        headers={
            "Origin": "https://app.vouch.test",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://app.vouch.test"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_production_hides_interactive_api_documentation() -> None:
    settings = Settings(
        _env_file=None,
        environment=Environment.PRODUCTION,
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/vouch",
    )

    with TestClient(create_app(settings)) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
