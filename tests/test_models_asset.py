"""Model structure tests for assets and availability_windows (no live DB)."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Enum, Numeric

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models.asset import ListingStatus


def _table(name: str):
    return Base.metadata.tables[name]


def _check_sql(table_name: str) -> set[str]:
    return {
        str(constraint.sqltext)
        for constraint in _table(table_name).constraints
        if isinstance(constraint, CheckConstraint)
    }


def test_assets_table_in_metadata() -> None:
    assert "assets" in Base.metadata.tables


def test_availability_windows_table_in_metadata() -> None:
    assert "availability_windows" in Base.metadata.tables


def test_assets_daily_rate_is_numeric() -> None:
    col = _table("assets").c["daily_rate"]
    assert isinstance(col.type, Numeric)


def test_assets_deposit_amount_is_numeric() -> None:
    col = _table("assets").c["deposit_amount"]
    assert isinstance(col.type, Numeric)


def test_availability_windows_asset_id_fk_references_assets() -> None:
    col = _table("availability_windows").c["asset_id"]
    fk_targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "assets.id" in fk_targets


def test_asset_monetary_amounts_are_constrained() -> None:
    checks = _check_sql("assets")
    assert "daily_rate > 0" in checks
    assert "deposit_amount >= 0" in checks


def test_availability_window_has_valid_date_range() -> None:
    assert "starts_at <= ends_at" in _check_sql("availability_windows")


# --- Listing publication fields ---


def test_assets_listing_status_column_exists() -> None:
    col = _table("assets").c["listing_status"]
    assert isinstance(col.type, Enum)


def test_assets_listing_status_enum_values() -> None:
    col = _table("assets").c["listing_status"]
    assert set(col.type.enums) == {"draft", "review", "active", "paused", "rejected"}


def test_assets_listing_status_default_is_draft() -> None:
    col = _table("assets").c["listing_status"]
    # Server default is set to 'draft' — new rows are never accidentally active.
    assert col.server_default is not None
    assert "draft" in str(col.server_default.arg)


def test_assets_minimum_trust_tier_column_exists() -> None:
    _table("assets").c["minimum_trust_tier"]


def test_assets_minimum_trust_tier_constrained() -> None:
    assert "minimum_trust_tier BETWEEN 0 AND 2" in _check_sql("assets")


def test_assets_review_actor_id_column_exists() -> None:
    _table("assets").c["review_actor_id"]


def test_assets_reviewed_at_column_exists() -> None:
    _table("assets").c["reviewed_at"]


def test_assets_review_reason_column_exists() -> None:
    _table("assets").c["review_reason"]


def test_listing_status_enum_has_expected_members() -> None:
    assert set(ListingStatus) == {
        ListingStatus.draft,
        ListingStatus.review,
        ListingStatus.active,
        ListingStatus.paused,
        ListingStatus.rejected,
    }
