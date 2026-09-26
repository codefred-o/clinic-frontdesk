"""Model structure tests for bookings (no live DB)."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Enum, Numeric
from sqlalchemy.dialects.postgresql import ExcludeConstraint, dialect
from sqlalchemy.schema import CreateTable

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


def test_booking_renter_and_vendor_ids_reference_users() -> None:
    table = _table("bookings")
    for column_name in ("renter_id", "vendor_id"):
        fk_targets = {fk.target_fullname for fk in table.c[column_name].foreign_keys}
        assert fk_targets == {"users.id"}


def _check_sql() -> set[str]:
    return {
        str(constraint.sqltext)
        for constraint in _table("bookings").constraints
        if isinstance(constraint, CheckConstraint)
    }


def test_booking_amounts_and_date_range_are_constrained() -> None:
    checks = _check_sql()
    assert "total_rental_fee > 0" in checks
    assert "deposit_amount >= 0" in checks
    assert "starts_on <= ends_on" in checks


def test_confirmed_and_active_bookings_cannot_overlap() -> None:
    constraints = [
        constraint
        for constraint in _table("bookings").constraints
        if isinstance(constraint, ExcludeConstraint)
    ]
    assert len(constraints) == 1
    constraint = constraints[0]
    assert constraint.name == "ex_bookings_no_active_asset_overlap"
    assert str(constraint.where) == "status IN ('confirmed', 'active')"
    compiled = str(CreateTable(constraint.table).compile(dialect=dialect()))
    assert "asset_id WITH =" in compiled
    assert "daterange(starts_on, ends_on, '[]') WITH &&" in compiled
