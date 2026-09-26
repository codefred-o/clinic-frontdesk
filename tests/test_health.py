"""Dependency-aware readiness tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.routes import health


def test_readiness_reports_database_available(
    client: TestClient,
    monkeypatch,
) -> None:
    async def ready(_engine) -> bool:
        return True

    monkeypatch.setattr(health, "database_is_ready", ready)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Vouch Test API",
        "version": "9.9.9",
        "checks": {"database": "ok"},
    }


def test_readiness_returns_503_when_database_is_unavailable(
    client: TestClient,
    monkeypatch,
) -> None:
    async def unavailable(_engine) -> bool:
        return False

    monkeypatch.setattr(health, "database_is_ready", unavailable)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert response.json()["checks"] == {"database": "unavailable"}
