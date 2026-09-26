"""Model structure tests for assets and availability_windows (no live DB)."""

from __future__ import annotations

from sqlalchemy import Numeric

import app.db.models  # noqa: F401
from app.db.base import Base


def _table(name: str):
    return Base.metadata.tables[name]


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
