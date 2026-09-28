"""ORM models for assets and availability windows."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin


class AssetCategory(StrEnum):
    camera = "camera"
    lens = "lens"
    lighting = "lighting"
    audio = "audio"
    drone = "drone"
    gimbal = "gimbal"
    other = "other"


class City(StrEnum):
    lagos = "lagos"
    abuja = "abuja"


class ListingStatus(StrEnum):
    """Publication state for a creative-gear listing.

    Visibility rules
    ----------------
    Only ``active`` listings owned by an active, non-deleted vendor and with
    ``is_available=True`` and ``city=lagos`` appear in public search results.

    Transition path (manual concierge only in Phase 0)
    ---------------------------------------------------
    draft  →  review  →  active
                      →  rejected
           →  (vendor edits, stays draft)
    active →  paused
    paused →  active (re-review may be required)
    """

    draft = "draft"
    review = "review"
    active = "active"
    paused = "paused"
    rejected = "rejected"


class Asset(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[AssetCategory] = mapped_column(
        Enum(AssetCategory, name="assetcategory"),
        nullable=False,
    )
    serial_number: Mapped[str | None] = mapped_column(nullable=True)
    daily_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    deposit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    city: Mapped[City] = mapped_column(
        Enum(City, name="city"),
        nullable=False,
    )
    condition_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Listing publication fields (added in migration 0002) ---
    listing_status: Mapped[ListingStatus] = mapped_column(
        Enum(ListingStatus, name="listingstatus"),
        nullable=False,
        default=ListingStatus.draft,
        server_default=ListingStatus.draft.value,
    )
    # Minimum renter trust tier required to transact on this asset (0, 1, or 2).
    # Stored as a plain integer to match the KYC tier policy.
    minimum_trust_tier: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    # Provenance of the most recent review decision (admin user ID, nullable).
    review_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("daily_rate > 0", name="ck_assets_daily_rate_positive"),
        CheckConstraint("deposit_amount >= 0", name="ck_assets_deposit_amount_nonnegative"),
        CheckConstraint(
            "minimum_trust_tier BETWEEN 0 AND 2",
            name="ck_assets_minimum_trust_tier_valid",
        ),
        # Partial index for public Lagos inventory search (active, non-deleted, available).
        Index(
            "ix_assets_public_lagos",
            "city",
            "category",
            "daily_rate",
            "created_at",
            "id",
            postgresql_where=text(
                "listing_status = 'active' AND is_available = true AND deleted_at IS NULL"
            ),
        ),
        Index("ix_assets_vendor_id", "vendor_id"),
    )

    vendor: Mapped[object] = relationship(
        "User",
        foreign_keys=[vendor_id],
        back_populates="assets",
        lazy="raise",
    )
    review_actor: Mapped[object] = relationship(
        "User",
        foreign_keys=[review_actor_id],
        lazy="raise",
    )
    bookings: Mapped[list[object]] = relationship(
        "Booking",
        back_populates="asset",
        lazy="raise",
    )
    availability_windows: Mapped[list[object]] = relationship(
        "AvailabilityWindow",
        back_populates="asset",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return (
            f"<Asset id={self.id} name={self.name!r} "
            f"vendor_id={self.vendor_id} category={self.category.value} "
            f"listing_status={self.listing_status.value}>"
        )


class AvailabilityWindow(TimestampMixin, Base):
    __tablename__ = "availability_windows"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id"),
        nullable=False,
    )
    starts_at: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    ends_at: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    __table_args__ = (
        CheckConstraint(
            "starts_at <= ends_at",
            name="ck_availability_windows_valid_date_range",
        ),
        Index("ix_availability_windows_asset_id", "asset_id"),
    )

    asset: Mapped[object] = relationship(
        "Asset",
        back_populates="availability_windows",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return (
            f"<AvailabilityWindow id={self.id} asset_id={self.asset_id} "
            f"starts_at={self.starts_at} ends_at={self.ends_at}>"
        )
