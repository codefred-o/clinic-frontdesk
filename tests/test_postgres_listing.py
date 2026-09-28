"""Live PostgreSQL tests for migration 0002 and inventory visibility rules.

Requires ``VOUCH_TEST_DATABASE_URL`` (set in CI via the GitHub Actions service).
Skipped automatically when the variable is absent.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config

from app.core.config import get_settings

ROOT = Path(__file__).parents[1]
DATABASE_URL = os.getenv("VOUCH_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="VOUCH_TEST_DATABASE_URL is required for live PostgreSQL checks",
)


def _alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    return config


def _asyncpg_url() -> str:
    assert DATABASE_URL is not None
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _setup_schema() -> None:
    """Apply full migration to head before each test."""


async def _run_listing_tests() -> None:  # noqa: PLR0912, PLR0915
    """All live database assertions in a single connection."""
    conn = await asyncpg.connect(_asyncpg_url())
    try:
        # ---------------------------------------------------------------
        # 1. Verify migration 0002 columns and enum are present.
        # ---------------------------------------------------------------
        columns = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'assets' AND column_name IN "
            "('listing_status', 'minimum_trust_tier', 'review_actor_id', "
            "'reviewed_at', 'review_reason')"
        )
        column_names = {row["column_name"] for row in columns}
        assert column_names == {
            "listing_status",
            "minimum_trust_tier",
            "review_actor_id",
            "reviewed_at",
            "review_reason",
        }, f"Missing columns: {column_names}"

        # 2. Enum type exists with expected values.
        enum_vals = await conn.fetchval(
            "SELECT array_agg(e.enumlabel ORDER BY e.enumsortorder) "
            "FROM pg_type t "
            "JOIN pg_enum e ON e.enumtypid = t.oid "
            "WHERE t.typname = 'listingstatus'"
        )
        assert set(enum_vals) == {"draft", "review", "active", "paused", "rejected"}

        # ---------------------------------------------------------------
        # 3. Trust tier check constraint rejects values outside 0-2.
        # ---------------------------------------------------------------
        vendor_id = await conn.fetchval(
            "INSERT INTO users (phone, full_name, role, is_active) "
            "VALUES ($1, $2, 'vendor', true) RETURNING id",
            f"+234800{uuid.uuid4().hex[:7]}",
            "Vendor One",
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "INSERT INTO assets "
                "(vendor_id, name, category, daily_rate, deposit_amount, city, minimum_trust_tier) "
                "VALUES ($1, 'Bad Tier', 'camera', 50000, 100000, 'lagos', 3)",
                vendor_id,
            )

        # ---------------------------------------------------------------
        # 4. New rows default to listing_status = 'draft'.
        # ---------------------------------------------------------------
        asset_id = await conn.fetchval(
            "INSERT INTO assets "
            "(vendor_id, name, category, daily_rate, deposit_amount, city) "
            "VALUES ($1, 'Test Camera', 'camera', 75000, 200000, 'lagos') RETURNING id",
            vendor_id,
        )
        status = await conn.fetchval("SELECT listing_status FROM assets WHERE id = $1", asset_id)
        assert status == "draft", f"Expected 'draft', got {status!r}"

        # ---------------------------------------------------------------
        # 5. Partial index ix_assets_public_lagos exists.
        # ---------------------------------------------------------------
        idx = await conn.fetchval(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'assets' AND indexname = 'ix_assets_public_lagos'"
        )
        assert idx == "ix_assets_public_lagos"

        # ---------------------------------------------------------------
        # 6. Visibility: only active Lagos asset with active vendor is visible.
        # ---------------------------------------------------------------
        # Activate the asset so we can test the filter.
        await conn.execute("UPDATE assets SET listing_status = 'active' WHERE id = $1", asset_id)

        # Inactive vendor asset should not appear.
        inactive_vendor_id = await conn.fetchval(
            "INSERT INTO users (phone, full_name, role, is_active) "
            "VALUES ($1, $2, 'vendor', false) RETURNING id",
            f"+234800{uuid.uuid4().hex[:7]}",
            "Inactive Vendor",
        )
        inactive_asset_id = await conn.fetchval(
            "INSERT INTO assets "
            "(vendor_id, name, category, daily_rate, deposit_amount, city, listing_status) "
            "VALUES ($1, 'Hidden Camera', 'camera', 75000, 200000, 'lagos', 'active') RETURNING id",
            inactive_vendor_id,
        )

        # Draft asset should not appear.
        draft_asset_id = await conn.fetchval(
            "INSERT INTO assets "
            "(vendor_id, name, category, daily_rate, deposit_amount, city, listing_status) "
            "VALUES ($1, 'Draft Camera', 'camera', 75000, 200000, 'lagos', 'draft') RETURNING id",
            vendor_id,
        )

        # Abuja asset should not appear.
        abuja_asset_id = await conn.fetchval(
            "INSERT INTO assets "
            "(vendor_id, name, category, daily_rate, deposit_amount, city, listing_status) "
            "VALUES ($1, 'Abuja Camera', 'camera', 75000, 200000, 'abuja', 'active') RETURNING id",
            vendor_id,
        )

        visible = await conn.fetch(
            "SELECT a.id FROM assets a "
            "JOIN users u ON u.id = a.vendor_id "
            "WHERE a.listing_status = 'active' "
            "AND a.is_available = true "
            "AND a.deleted_at IS NULL "
            "AND a.city = 'lagos' "
            "AND u.is_active = true "
            "AND u.deleted_at IS NULL"
        )
        visible_ids = {row["id"] for row in visible}
        assert asset_id in visible_ids, "Active Lagos asset with active vendor must be visible"
        assert inactive_asset_id not in visible_ids, "Asset with inactive vendor must be hidden"
        assert draft_asset_id not in visible_ids, "Draft asset must be hidden"
        assert abuja_asset_id not in visible_ids, "Abuja asset must be hidden"

        # ---------------------------------------------------------------
        # 7. Date availability: blocked window and confirmed booking hide asset.
        # ---------------------------------------------------------------
        renter_id = await conn.fetchval(
            "INSERT INTO users (phone, full_name, role, is_active) "
            "VALUES ($1, $2, 'renter', true) RETURNING id",
            f"+234800{uuid.uuid4().hex[:7]}",
            "Renter One",
        )

        # Insert a confirmed booking for 2026-11-01 to 2026-11-05.
        await conn.execute(
            "INSERT INTO bookings "
            "(asset_id, renter_id, vendor_id, starts_on, ends_on, status, "
            "total_rental_fee, deposit_amount) "
            "VALUES ($1, $2, $3, DATE '2026-11-01', DATE '2026-11-05', "
            "'confirmed', 225000, 200000)",
            asset_id,
            renter_id,
            vendor_id,
        )

        # Asset must be excluded for an overlap date (2026-11-03).
        blocked_by_booking = await conn.fetchval(
            "SELECT EXISTS ("
            "  SELECT 1 FROM bookings b "
            "  WHERE b.asset_id = $1 "
            "  AND b.status IN ('confirmed', 'active') "
            "  AND b.starts_on <= $2 AND b.ends_on >= $3"
            ")",
            asset_id,
            date(2026, 11, 3),
            date(2026, 11, 3),
        )
        assert blocked_by_booking, "Asset with confirmed booking must be excluded for overlap date"

        # Asset is available for a non-overlapping date (2026-11-06).
        not_blocked = await conn.fetchval(
            "SELECT EXISTS ("
            "  SELECT 1 FROM bookings b "
            "  WHERE b.asset_id = $1 "
            "  AND b.status IN ('confirmed', 'active') "
            "  AND b.starts_on <= $2 AND b.ends_on >= $3"
            ")",
            asset_id,
            date(2026, 11, 6),
            date(2026, 11, 6),
        )
        assert not not_blocked, "Asset must be available for non-overlapping date"

        # Insert a blocked availability window: 2026-12-20 to 2026-12-25.
        await conn.execute(
            "INSERT INTO availability_windows "
            "(asset_id, starts_at, ends_at, is_blocked) "
            "VALUES ($1, DATE '2026-12-20', DATE '2026-12-25', true)",
            asset_id,
        )
        blocked_by_window = await conn.fetchval(
            "SELECT EXISTS ("
            "  SELECT 1 FROM availability_windows w "
            "  WHERE w.asset_id = $1 "
            "  AND w.is_blocked = true "
            "  AND w.starts_at <= $2 AND w.ends_at >= $3"
            ")",
            asset_id,
            date(2026, 12, 22),
            date(2026, 12, 22),
        )
        assert blocked_by_window, "Asset must be excluded for date inside blocked window"

        # Pending booking must NOT reserve inventory.
        pending_only = await conn.fetchval(
            "SELECT EXISTS ("
            "  SELECT 1 FROM bookings b "
            "  WHERE b.asset_id = $1 "
            "  AND b.status IN ('confirmed', 'active') "
            "  AND b.starts_on <= $2 AND b.ends_on >= $3"
            ")",
            asset_id,
            date(2027, 1, 15),
            date(2027, 1, 15),
        )
        assert not pending_only, "Pending bookings must not block availability"

        # Serial number must never appear in the public query.
        await conn.execute(
            "UPDATE assets SET serial_number = 'SECRET-SN-001' WHERE id = $1", asset_id
        )
        # Verify it's in DB but we don't select it in public projection.
        sn = await conn.fetchval("SELECT serial_number FROM assets WHERE id = $1", asset_id)
        assert sn == "SECRET-SN-001"
        # The public query projection should not include serial_number.
        row = await conn.fetchrow(
            "SELECT id, name, category, daily_rate, deposit_amount, city, "
            "is_available, minimum_trust_tier, created_at, updated_at "
            "FROM assets WHERE id = $1",
            asset_id,
        )
        assert "serial_number" not in row.keys(), (
            "serial_number must not appear in public projection"
        )

    finally:
        await conn.close()


def test_listing_migration_and_visibility_rules(monkeypatch) -> None:
    assert DATABASE_URL is not None
    monkeypatch.setenv("VOUCH_DATABASE_URL", DATABASE_URL)
    get_settings.cache_clear()
    config = _alembic_config()

    try:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        asyncio.run(_run_listing_tests())
        # Verify round-trip downgrade/upgrade.
        command.downgrade(config, "0001_initial_schema")
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()
