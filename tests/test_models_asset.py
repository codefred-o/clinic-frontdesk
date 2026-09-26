"""Model structure tests for assets and availability_windows (no live DB)."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Numeric

import app.db.models  # noqa: F401
from app.db.base import Base


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
