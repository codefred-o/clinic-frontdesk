"""Public inventory query service.

Encapsulates the SQL logic for the public Lagos asset search and detail
endpoints.  All visibility rules are applied in one place so there is no
risk of leaking non-public data through partial filtering.

Visibility rules applied here
------------------------------
1. ``listing_status = 'active'``
2. ``assets.is_available = TRUE``
3. ``assets.deleted_at IS NULL``
4. ``assets.city = 'lagos'``
5. Owning vendor: ``users.is_active = TRUE AND users.deleted_at IS NULL``

Date-range filter (when both ``starts_on`` and ``ends_on`` are provided)
--------------------------------------------------------------------------
* Exclude assets with a blocked availability window overlapping the range.
* Exclude assets with a confirmed or active booking overlapping the range.
  Overlap check: ``starts_at/starts_on <= ends_on AND ends_at/ends_on >= starts_on``
  (both ends inclusive, matching the GiST exclusion semantics).

Cursor pagination
-----------------
Pages are ordered by ``(created_at ASC, id ASC)``.  The opaque cursor encodes
the ``(created_at, id)`` of the last returned item and is decoded by
:mod:`app.schemas.pagination`.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import and_, exists, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.asset import Asset, AvailabilityWindow, City, ListingStatus
from app.db.models.booking import Booking, BookingStatus
from app.db.models.user import User
from app.schemas.pagination import MAX_PAGE_LIMIT, decode_cursor, encode_cursor


@dataclass
class AssetPage:
    """Result of a single inventory page query."""

    items: list[Asset]
    next_cursor: str | None


# ---------------------------------------------------------------------------
# Internal predicate builder
# ---------------------------------------------------------------------------


def _public_visibility_clauses(query):
    """Return the WHERE clauses that apply to all public asset queries."""
    return (
        query.where(
            Asset.listing_status == ListingStatus.active,
            Asset.is_available.is_(True),
            Asset.deleted_at.is_(None),
            Asset.city == City.lagos,
        )
        .join(
            User,
            User.id == Asset.vendor_id,
        )
        .where(
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )


def _date_overlap_clauses(asset_id_col, starts_on: datetime.date, ends_on: datetime.date):
    """Return EXISTS sub-predicates that block assets with date conflicts."""
    # Blocked availability window overlapping [starts_on, ends_on] inclusive.
    blocked_window = exists(
        select(AvailabilityWindow.id).where(
            AvailabilityWindow.asset_id == asset_id_col,
            AvailabilityWindow.is_blocked.is_(True),
            AvailabilityWindow.starts_at <= ends_on,
            AvailabilityWindow.ends_at >= starts_on,
        )
    )

    # Confirmed or active booking overlapping [starts_on, ends_on] inclusive.
    active_booking = exists(
        select(Booking.id).where(
            Booking.asset_id == asset_id_col,
            Booking.status.in_([BookingStatus.confirmed, BookingStatus.active]),
            Booking.starts_on <= ends_on,
            Booking.ends_on >= starts_on,
        )
    )

    return not_(blocked_window), not_(active_booking)


# ---------------------------------------------------------------------------
# Public query functions
# ---------------------------------------------------------------------------


async def search_public_assets(
    session: AsyncSession,
    *,
    category: str | None = None,
    starts_on: datetime.date | None = None,
    ends_on: datetime.date | None = None,
    min_daily_rate: Decimal | None = None,
    max_daily_rate: Decimal | None = None,
    limit: int = 20,
    cursor: str | None = None,
) -> AssetPage:
    """Return a page of publicly visible Lagos assets matching the filters.

    Parameters
    ----------
    session:
        An active async SQLAlchemy session.
    category:
        Optional ``AssetCategory`` value string filter.
    starts_on / ends_on:
        Inclusive date range for availability filtering.  Both must be provided
        together; if only one is given, the date filter is skipped (callers
        should validate before calling).
    min_daily_rate / max_daily_rate:
        Inclusive rate bounds (NGN, compared to ``assets.daily_rate``).
    limit:
        Number of items per page (1–100).
    cursor:
        Opaque pagination cursor from a previous response.

    Returns
    -------
    AssetPage
        Matched assets plus an optional ``next_cursor`` for the following page.
    """
    limit = min(limit, MAX_PAGE_LIMIT)

    stmt = select(Asset)
    stmt = _public_visibility_clauses(stmt)

    if category is not None:
        stmt = stmt.where(Asset.category == category)

    if min_daily_rate is not None:
        stmt = stmt.where(Asset.daily_rate >= min_daily_rate)

    if max_daily_rate is not None:
        stmt = stmt.where(Asset.daily_rate <= max_daily_rate)

    if starts_on is not None and ends_on is not None:
        no_block, no_active = _date_overlap_clauses(Asset.id, starts_on, ends_on)
        stmt = stmt.where(no_block, no_active)

    # Cursor: items after the encoded (created_at, id) position.
    if cursor is not None:
        created_at_iso, id_str = decode_cursor(cursor)
        cursor_dt = datetime.datetime.fromisoformat(created_at_iso)
        cursor_id = uuid.UUID(id_str)
        stmt = stmt.where(
            and_(
                Asset.created_at >= cursor_dt,
                # When created_at is identical, use id as tiebreaker.
                ~and_(Asset.created_at == cursor_dt, Asset.id <= cursor_id),
            )
        )

    # Deterministic ordering: (created_at ASC, id ASC).
    stmt = stmt.order_by(Asset.created_at.asc(), Asset.id.asc())

    # Fetch one extra to detect whether a next page exists.
    stmt = stmt.limit(limit + 1)

    result = await session.execute(stmt)
    rows: list[Asset] = list(result.scalars().all())

    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = encode_cursor(last.created_at.isoformat(), str(last.id))
    else:
        next_cursor = None

    return AssetPage(items=rows, next_cursor=next_cursor)


async def get_public_asset(session: AsyncSession, asset_id: uuid.UUID) -> Asset:
    """Return a single publicly visible asset or raise ``ResourceNotFoundError``.

    Raises :class:`app.schemas.errors.ResourceNotFoundError` when the asset is
    absent, soft-deleted, non-active, Abuja, or owned by an inactive vendor —
    making all hidden states indistinguishable from a genuine 404.
    """
    from app.schemas.errors import ResourceNotFoundError

    stmt = select(Asset).where(Asset.id == asset_id)
    stmt = _public_visibility_clauses(stmt)

    result = await session.execute(stmt)
    asset = result.scalar_one_or_none()

    if asset is None:
        raise ResourceNotFoundError()

    return asset
