"""Model structure tests for bookings (no live DB)."""

from __future__ import annotations

from sqlalchemy import Enum, Numeric

import app.db.models  # noqa: F401
from app.db.base import Base


def _table(name: str):
    return Base.metadata.tables[name]


def test_bookings_table_in_metadata() -> None:
    assert "bookings" in Base.metadata.tables


def test_booking_status_is_enum_type() -> None:
    col = _table("bookings").c["status"]
    assert isinstance(col.type, Enum)


def test_booking_total_rental_fee_is_numeric() -> None:
    col = _table("bookings").c["total_rental_fee"]
    assert isinstance(col.type, Numeric)


def test_booking_asset_id_fk_references_assets() -> None:
    col = _table("bookings").c["asset_id"]
    fk_targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "assets.id" in fk_targets


def test_booking_renter_id_fk_references_users() -> None:
    col = _table("bookings").c["renter_id"]
    fk_targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "users.id" in fk_targets
