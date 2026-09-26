"""ORM models for assets and availability windows."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Index, Numeric, Text, text
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

    __table_args__ = (Index("ix_assets_vendor_id", "vendor_id"),)

    vendor: Mapped[object] = relationship(
        "User",
        back_populates="assets",
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
            f"vendor_id={self.vendor_id} category={self.category.value}>"
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

    __table_args__ = (Index("ix_availability_windows_asset_id", "asset_id"),)

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
