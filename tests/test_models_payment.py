"""Model structure tests for payments (no live DB)."""

from __future__ import annotations

from sqlalchemy import Enum
from sqlalchemy.dialects.postgresql import JSONB

import app.db.models  # noqa: F401
from app.db.base import Base


def _table(name: str):
    return Base.metadata.tables[name]


def test_payments_table_in_metadata() -> None:
    assert "payments" in Base.metadata.tables


def test_payments_type_is_enum() -> None:
    col = _table("payments").c["type"]
    assert isinstance(col.type, Enum)


def test_payments_metadata_is_jsonb() -> None:
    col = _table("payments").c["metadata"]
    assert isinstance(col.type, JSONB)


def test_payments_booking_id_fk_references_bookings() -> None:
    col = _table("payments").c["booking_id"]
    fk_targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "bookings.id" in fk_targets
