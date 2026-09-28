"""Public-facing schemas for the asset inventory endpoints.

Visibility contract (public search and detail)
----------------------------------------------
An asset is publicly visible when ALL of the following hold:

1. ``listing_status = 'active'``
2. ``is_available = True``
3. ``deleted_at IS NULL``
4. ``city = 'lagos'``  (Abuja is not yet launched)
5. The owning vendor has ``is_active = True`` and ``deleted_at IS NULL``.

Date availability (when ``starts_on`` + ``ends_on`` filters are supplied)
--------------------------------------------------------------------------
* An asset is excluded from results for the requested date range when any
  ``AvailabilityWindow`` with ``is_blocked = True`` overlaps the range
  (inclusive on both ends: ``starts_at <= ends_on AND ends_at >= starts_on``).
* An asset is also excluded when any ``Booking`` in status ``confirmed`` or
  ``active`` overlaps the range inclusively.
* Positive ``AvailabilityWindow`` rows (``is_blocked = False``) do NOT create
  an allowlist — the absence of blocks is sufficient.
* Bookings in status ``pending``, ``completed``, ``cancelled``, or ``disputed``
  do NOT reserve inventory.

Restricted fields (never serialised in public responses)
--------------------------------------------------------
``serial_number``, ``vendor_id``, ``condition_notes``, ``review_actor_id``,
``reviewed_at``, ``review_reason``, ``listing_status``, ``deleted_at``.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer

# Page-size bounds used by routes and the filter model.
MAX_LIMIT = 100
DEFAULT_LIMIT = 20


class PublicAsset(BaseModel):
    """Safe public projection of a creative-gear listing."""

    id: uuid.UUID
    name: str
    description: str | None
    category: str
    daily_rate: Decimal
    deposit_amount: Decimal
    currency: str = "NGN"
    city: str
    is_available: bool
    minimum_trust_tier: int = Field(
        description="Minimum renter trust tier required to transact on this asset (0, 1, or 2)."
    )
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @field_serializer("daily_rate", "deposit_amount")
    def _serialize_decimal(self, v: Decimal) -> str:
        """Amounts are serialised as decimal strings per the API contract."""
        return f"{v:.2f}"

    model_config = {"from_attributes": True}


class AssetSearchFilters(BaseModel):
    """Validated query parameters for ``GET /api/v1/assets``."""

    category: str | None = None
    starts_on: datetime.date | None = None
    ends_on: datetime.date | None = None
    min_daily_rate: Decimal | None = None
    max_daily_rate: Decimal | None = None
    limit: int = Field(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    cursor: str | None = None
