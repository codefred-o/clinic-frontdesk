"""Model structure tests for users and kyc_profiles (no live DB)."""

from __future__ import annotations

from sqlalchemy import Integer

import app.db.models  # noqa: F401 — registers all models
from app.db.base import Base


def _table(name: str):
    return Base.metadata.tables[name]


def test_users_table_in_metadata() -> None:
    assert "users" in Base.metadata.tables


def test_kyc_profiles_table_in_metadata() -> None:
    assert "kyc_profiles" in Base.metadata.tables


def test_users_phone_is_indexed_and_unique() -> None:
    phone_col = _table("users").c["phone"]
    assert phone_col.unique is True
    # index defined via __table_args__
    index_names = {idx.name for idx in _table("users").indexes}
    assert "ix_users_phone" in index_names


def test_kyc_profiles_user_id_fk_references_users() -> None:
    user_id_col = _table("kyc_profiles").c["user_id"]
    fk_targets = {fk.target_fullname for fk in user_id_col.foreign_keys}
    assert "users.id" in fk_targets


def test_kyc_profiles_tier_column_has_integer_type_and_default() -> None:
    tier_col = _table("kyc_profiles").c["tier"]
    assert isinstance(tier_col.type, Integer)
    assert tier_col.default.arg == 0
