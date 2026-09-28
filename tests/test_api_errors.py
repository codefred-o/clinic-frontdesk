"""Tests for the shared API error envelope and request-ID propagation."""

from __future__ import annotations

import uuid

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.config import Environment, Settings
from app.main import create_app
from app.schemas.errors import InvalidRequestError, ResourceNotFoundError

# ---------------------------------------------------------------------------
# Minimal fixture app that exposes error-triggering routes.
# ---------------------------------------------------------------------------


def _make_client_with_error_routes() -> TestClient:
    """Build a TestClient with extra routes that raise domain exceptions."""
    settings = Settings(
        _env_file=None,
        app_name="Vouch Error Test",
        app_version="0.0.0",
        environment=Environment.TEST,
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/vouch_test",
        cors_origins=["https://app.vouch.test"],
    )
    app = create_app(settings)

    test_router = APIRouter(prefix="/test-errors")

    @test_router.get("/not-found")
    async def _raise_not_found():
        raise ResourceNotFoundError()

    @test_router.get("/bad-request")
    async def _raise_bad_request():
        raise InvalidRequestError(message="Nope.", details={"field": "city", "reason": "invalid"})

    app.include_router(test_router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def error_client() -> TestClient:
    return _make_client_with_error_routes()


# ---------------------------------------------------------------------------
# Error envelope structure tests
# ---------------------------------------------------------------------------


def test_not_found_returns_404(error_client: TestClient) -> None:
    resp = error_client.get("/test-errors/not-found")
    assert resp.status_code == 404


def test_not_found_has_correct_code(error_client: TestClient) -> None:
    resp = error_client.get("/test-errors/not-found")
    assert resp.json()["error"]["code"] == "resource_not_found"


def test_not_found_has_details_object(error_client: TestClient) -> None:
    resp = error_client.get("/test-errors/not-found")
    assert isinstance(resp.json()["error"]["details"], dict)


def test_bad_request_returns_400(error_client: TestClient) -> None:
    resp = error_client.get("/test-errors/bad-request")
    assert resp.status_code == 400


def test_bad_request_has_correct_code(error_client: TestClient) -> None:
    resp = error_client.get("/test-errors/bad-request")
    assert resp.json()["error"]["code"] == "invalid_request"


def test_bad_request_has_structured_details(error_client: TestClient) -> None:
    resp = error_client.get("/test-errors/bad-request")
    details = resp.json()["error"]["details"]
    assert details["field"] == "city"


# ---------------------------------------------------------------------------
# Request-ID propagation
# ---------------------------------------------------------------------------


def test_supplied_request_id_is_echoed_in_response_header(error_client: TestClient) -> None:
    req_id = "req-test-001"
    resp = error_client.get("/test-errors/not-found", headers={"X-Request-ID": req_id})
    assert resp.headers.get("X-Request-ID") == req_id


def test_supplied_request_id_is_echoed_in_error_body(error_client: TestClient) -> None:
    req_id = "req-test-002"
    resp = error_client.get("/test-errors/not-found", headers={"X-Request-ID": req_id})
    assert resp.json()["error"]["request_id"] == req_id


def test_header_and_body_request_id_are_identical(error_client: TestClient) -> None:
    req_id = "req-test-003"
    resp = error_client.get("/test-errors/bad-request", headers={"X-Request-ID": req_id})
    body_id = resp.json()["error"]["request_id"]
    header_id = resp.headers.get("X-Request-ID")
    assert body_id == header_id == req_id


def test_invalid_request_id_is_replaced_with_uuid(error_client: TestClient) -> None:
    """A control-character or oversized request ID must be replaced, not echoed."""
    bad_id = "\x00bad"  # control character — invalid per the spec
    resp = error_client.get("/test-errors/not-found", headers={"X-Request-ID": bad_id})
    returned_id = resp.headers.get("X-Request-ID", "")
    # Must not echo the bad ID.
    assert returned_id != bad_id
    # Must be a valid UUID4 string.
    uuid.UUID(returned_id)  # raises if invalid


def test_missing_request_id_receives_generated_uuid(error_client: TestClient) -> None:
    resp = error_client.get("/test-errors/not-found")
    returned_id = resp.headers.get("X-Request-ID", "")
    uuid.UUID(returned_id)  # raises if invalid


def test_error_body_does_not_contain_traceback(error_client: TestClient) -> None:
    resp = error_client.get("/test-errors/not-found")
    body_text = resp.text
    assert "traceback" not in body_text.lower()
    assert "exception" not in body_text.lower()
    assert "sqlalchemy" not in body_text.lower()
