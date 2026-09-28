"""API tests for the public inventory endpoints.

Uses the TestClient with a patched service layer so no live PostgreSQL is
required.  Field-restriction and filter logic is asserted through the API
contract; real SQL behavior is covered by ``test_postgres_listing.py``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from app.db.models.asset import AssetCategory, City, ListingStatus
from app.schemas.errors import ResourceNotFoundError
from app.schemas.pagination import encode_cursor

# ---------------------------------------------------------------------------
# Fake asset row helper
# ---------------------------------------------------------------------------


def _fake_asset(**overrides: Any) -> Any:
    """Return a simple namespace that looks enough like an Asset ORM row."""
    from types import SimpleNamespace

    now = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
    defaults = dict(
        id=uuid.uuid4(),
        name="Sony FX3",
        description="Camera body",
        category=AssetCategory.camera,
        daily_rate=Decimal("75000.00"),
        deposit_amount=Decimal("200000.00"),
        is_available=True,
        city=City.lagos,
        minimum_trust_tier=1,
        listing_status=ListingStatus.active,
        created_at=now,
        updated_at=now,
        # Restricted fields that must never appear in public output:
        serial_number="SECRET-SN-001",
        vendor_id=uuid.uuid4(),
        condition_notes="Minor mark",
        review_actor_id=None,
        reviewed_at=None,
        review_reason=None,
        deleted_at=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Collection endpoint tests (GET /api/v1/assets)
# ---------------------------------------------------------------------------


def test_list_assets_returns_200(client: TestClient, monkeypatch) -> None:
    asset = _fake_asset()

    async def mock_search(*args, **kwargs):
        from app.services.inventory import AssetPage

        return AssetPage(items=[asset], next_cursor=None)

    monkeypatch.setattr("app.api.routes.assets.search_public_assets", mock_search)
    resp = client.get("/api/v1/assets")
    assert resp.status_code == 200


def test_list_assets_returns_items_and_pagination(client: TestClient, monkeypatch) -> None:
    asset = _fake_asset()

    async def mock_search(*args, **kwargs):
        from app.services.inventory import AssetPage

        return AssetPage(items=[asset], next_cursor=None)

    monkeypatch.setattr("app.api.routes.assets.search_public_assets", mock_search)
    body = client.get("/api/v1/assets").json()
    assert "items" in body
    assert "pagination" in body
    assert body["pagination"]["next_cursor"] is None


def test_list_assets_response_excludes_restricted_fields(client: TestClient, monkeypatch) -> None:
    """Restricted fields must never appear in public collection output."""
    asset = _fake_asset()

    async def mock_search(*args, **kwargs):
        from app.services.inventory import AssetPage

        return AssetPage(items=[asset], next_cursor=None)

    monkeypatch.setattr("app.api.routes.assets.search_public_assets", mock_search)
    item = client.get("/api/v1/assets").json()["items"][0]

    restricted = {
        "serial_number",
        "vendor_id",
        "condition_notes",
        "review_actor_id",
        "reviewed_at",
        "review_reason",
        "listing_status",
        "deleted_at",
    }
    for field in restricted:
        assert field not in item, f"Restricted field '{field}' must not appear in public output"


def test_list_assets_includes_required_public_fields(client: TestClient, monkeypatch) -> None:
    asset = _fake_asset()

    async def mock_search(*args, **kwargs):
        from app.services.inventory import AssetPage

        return AssetPage(items=[asset], next_cursor=None)

    monkeypatch.setattr("app.api.routes.assets.search_public_assets", mock_search)
    item = client.get("/api/v1/assets").json()["items"][0]

    required = {
        "id",
        "name",
        "category",
        "daily_rate",
        "deposit_amount",
        "city",
        "is_available",
        "minimum_trust_tier",
        "currency",
        "created_at",
        "updated_at",
    }
    for field in required:
        assert field in item, f"Required public field '{field}' is missing"


def test_list_assets_daily_rate_is_decimal_string(client: TestClient, monkeypatch) -> None:
    asset = _fake_asset()

    async def mock_search(*args, **kwargs):
        from app.services.inventory import AssetPage

        return AssetPage(items=[asset], next_cursor=None)

    monkeypatch.setattr("app.api.routes.assets.search_public_assets", mock_search)
    item = client.get("/api/v1/assets").json()["items"][0]
    # Must be a string (e.g. "75000.00"), not a float.
    assert isinstance(item["daily_rate"], str)
    assert "." in item["daily_rate"]


def test_list_assets_empty_result_returns_200(client: TestClient, monkeypatch) -> None:
    async def mock_search(*args, **kwargs):
        from app.services.inventory import AssetPage

        return AssetPage(items=[], next_cursor=None)

    monkeypatch.setattr("app.api.routes.assets.search_public_assets", mock_search)
    body = client.get("/api/v1/assets").json()
    assert body["items"] == []


def test_list_assets_returns_next_cursor_when_more_pages(client: TestClient, monkeypatch) -> None:
    cursor = encode_cursor("2026-10-01T12:00:00+00:00", str(uuid.uuid4()))

    async def mock_search(*args, **kwargs):
        from app.services.inventory import AssetPage

        return AssetPage(items=[_fake_asset()], next_cursor=cursor)

    monkeypatch.setattr("app.api.routes.assets.search_public_assets", mock_search)
    body = client.get("/api/v1/assets?limit=1").json()
    assert body["pagination"]["next_cursor"] == cursor


def test_list_assets_abuja_city_returns_400(client: TestClient, monkeypatch) -> None:
    async def mock_search(*args, **kwargs):
        from app.services.inventory import AssetPage

        return AssetPage(items=[], next_cursor=None)

    monkeypatch.setattr("app.api.routes.assets.search_public_assets", mock_search)
    resp = client.get("/api/v1/assets?city=abuja")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "invalid_request"
    assert body["error"]["details"]["reason"] == "abuja_not_yet_launched"


def test_list_assets_missing_ends_on_returns_400(client: TestClient, monkeypatch) -> None:
    async def mock_search(*args, **kwargs):
        from app.services.inventory import AssetPage

        return AssetPage(items=[], next_cursor=None)

    monkeypatch.setattr("app.api.routes.assets.search_public_assets", mock_search)
    resp = client.get("/api/v1/assets?starts_on=2026-11-01")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_request"


def test_list_assets_reversed_dates_returns_400(client: TestClient, monkeypatch) -> None:
    async def mock_search(*args, **kwargs):
        from app.services.inventory import AssetPage

        return AssetPage(items=[], next_cursor=None)

    monkeypatch.setattr("app.api.routes.assets.search_public_assets", mock_search)
    resp = client.get("/api/v1/assets?starts_on=2026-11-05&ends_on=2026-11-01")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_request"


def test_list_assets_malformed_cursor_returns_400(client: TestClient, monkeypatch) -> None:
    async def mock_search(*args, **kwargs):
        # This should raise CursorDecodeError before the service is reached.
        raise RuntimeError("Should not be called")

    monkeypatch.setattr("app.api.routes.assets.search_public_assets", mock_search)
    resp = client.get("/api/v1/assets?cursor=not-a-valid-cursor-xyz")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_cursor"


def test_list_assets_x_request_id_echoed(client: TestClient, monkeypatch) -> None:
    async def mock_search(*args, **kwargs):
        from app.services.inventory import AssetPage

        return AssetPage(items=[], next_cursor=None)

    monkeypatch.setattr("app.api.routes.assets.search_public_assets", mock_search)
    resp = client.get("/api/v1/assets", headers={"X-Request-ID": "req-inv-001"})
    assert resp.headers.get("X-Request-ID") == "req-inv-001"


# ---------------------------------------------------------------------------
# Detail endpoint tests (GET /api/v1/assets/{asset_id})
# ---------------------------------------------------------------------------


def test_get_asset_returns_200(client: TestClient, monkeypatch) -> None:
    asset = _fake_asset()

    async def mock_get(session, asset_id):
        return asset

    monkeypatch.setattr("app.api.routes.assets.get_public_asset", mock_get)
    resp = client.get(f"/api/v1/assets/{asset.id}")
    assert resp.status_code == 200


def test_get_asset_excludes_restricted_fields(client: TestClient, monkeypatch) -> None:
    asset = _fake_asset()

    async def mock_get(session, asset_id):
        return asset

    monkeypatch.setattr("app.api.routes.assets.get_public_asset", mock_get)
    body = client.get(f"/api/v1/assets/{asset.id}").json()

    restricted = {
        "serial_number",
        "vendor_id",
        "condition_notes",
        "review_actor_id",
        "reviewed_at",
        "review_reason",
        "listing_status",
        "deleted_at",
    }
    for field in restricted:
        assert field not in body, f"Restricted field '{field}' must not appear in detail output"


def test_get_asset_not_found_returns_404(client: TestClient, monkeypatch) -> None:
    async def mock_get(session, asset_id):
        raise ResourceNotFoundError()

    monkeypatch.setattr("app.api.routes.assets.get_public_asset", mock_get)
    resp = client.get(f"/api/v1/assets/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_get_asset_not_found_uses_safe_code(client: TestClient, monkeypatch) -> None:
    async def mock_get(session, asset_id):
        raise ResourceNotFoundError()

    monkeypatch.setattr("app.api.routes.assets.get_public_asset", mock_get)
    body = client.get(f"/api/v1/assets/{uuid.uuid4()}").json()
    assert body["error"]["code"] == "resource_not_found"


def test_get_asset_not_found_exposes_no_listing_state(client: TestClient, monkeypatch) -> None:
    async def mock_get(session, asset_id):
        raise ResourceNotFoundError()

    monkeypatch.setattr("app.api.routes.assets.get_public_asset", mock_get)
    body = client.get(f"/api/v1/assets/{uuid.uuid4()}").json()
    body_str = str(body)
    # Ensure no internal state is leaked.
    for word in ("draft", "paused", "rejected", "listing_status", "serial_number"):
        assert word not in body_str.lower(), f"Leaked internal state: {word}"


def test_get_asset_invalid_uuid_returns_422(client: TestClient, monkeypatch) -> None:
    """FastAPI should reject non-UUID path parameters with 422."""

    async def mock_get(session, asset_id):
        raise RuntimeError("Should not be reached")

    monkeypatch.setattr("app.api.routes.assets.get_public_asset", mock_get)
    resp = client.get("/api/v1/assets/not-a-uuid")
    assert resp.status_code == 422


def test_get_asset_currency_is_ngn(client: TestClient, monkeypatch) -> None:
    asset = _fake_asset()

    async def mock_get(session, asset_id):
        return asset

    monkeypatch.setattr("app.api.routes.assets.get_public_asset", mock_get)
    body = client.get(f"/api/v1/assets/{asset.id}").json()
    assert body["currency"] == "NGN"
