"""ORM model for the bookings table."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class BookingStatus(StrEnum):
    pending = "pending"
    confirmed = "confirmed"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"
    disputed = "disputed"


class Booking(TimestampMixin, Base):
    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id"),
        nullable=False,
    )
    renter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    starts_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="bookingstatus"),
        default=BookingStatus.pending,
        server_default=BookingStatus.pending.value,
        nullable=False,
    )
    total_rental_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    deposit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    platform_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_bookings_asset_id", "asset_id"),
        Index("ix_bookings_renter_id", "renter_id"),
    )

    asset: Mapped[object] = relationship(
        "Asset",
        back_populates="bookings",
        lazy="raise",
    )
    renter: Mapped[object] = relationship(
        "User",
        back_populates="bookings_as_renter",
        lazy="raise",
    )
    payments: Mapped[list[object]] = relationship(
        "Payment",
        back_populates="booking",
        lazy="raise",
    )
    handover_records: Mapped[list[object]] = relationship(
        "HandoverRecord",
        back_populates="booking",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return (
            f"<Booking id={self.id} asset_id={self.asset_id} "
            f"renter_id={self.renter_id} status={self.status.value}>"
        )
