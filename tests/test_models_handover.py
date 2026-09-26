"""Model structure tests for handover_records (no live DB)."""

from __future__ import annotations

from sqlalchemy import Enum
from sqlalchemy.dialects.postgresql import JSONB

import app.db.models  # noqa: F401
from app.db.base import Base


def _table(name: str):
    return Base.metadata.tables[name]


def test_handover_records_table_in_metadata() -> None:
    assert "handover_records" in Base.metadata.tables


def test_handover_direction_enum_db_values_include_pickup_and_return() -> None:
    col = _table("handover_records").c["direction"]
    assert isinstance(col.type, Enum)
    assert "pickup" in col.type.enums
    assert "return" in col.type.enums
    assert "return_" not in col.type.enums


def test_handover_condition_checklist_is_jsonb() -> None:
    col = _table("handover_records").c["condition_checklist"]
    assert isinstance(col.type, JSONB)


def test_handover_booking_id_fk_references_bookings() -> None:
    col = _table("handover_records").c["booking_id"]
    fk_targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "bookings.id" in fk_targets
