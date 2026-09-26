"""ORM model for the bookings table."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


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
    vendor_id: Mapped[uuid.UUID] = mapped_column(
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
        CheckConstraint("total_rental_fee > 0", name="ck_bookings_total_rental_fee_positive"),
        CheckConstraint("deposit_amount >= 0", name="ck_bookings_deposit_amount_nonnegative"),
        CheckConstraint("starts_on <= ends_on", name="ck_bookings_valid_date_range"),
        ExcludeConstraint(
            ("asset_id", "="),
            (text("daterange(starts_on, ends_on, '[]')"), "&&"),
            where=text("status IN ('confirmed', 'active')"),
            name="ex_bookings_no_active_asset_overlap",
            using="gist",
        ),
        Index("ix_bookings_asset_id", "asset_id"),
        Index("ix_bookings_renter_id", "renter_id"),
        Index("ix_bookings_vendor_id", "vendor_id"),
        UniqueConstraint("id", "renter_id", name="uq_bookings_id_renter"),
        UniqueConstraint("id", "vendor_id", name="uq_bookings_id_vendor"),
    )

    asset: Mapped[object] = relationship(
        "Asset",
        back_populates="bookings",
        lazy="raise",
    )
    renter: Mapped[object] = relationship(
        "User",
        foreign_keys=[renter_id],
        back_populates="bookings_as_renter",
        lazy="raise",
    )
    vendor: Mapped[object] = relationship(
        "User",
        foreign_keys=[vendor_id],
        back_populates="bookings_as_vendor",
        lazy="raise",
    )
    payments: Mapped[list[object]] = relationship(
        "Payment",
        back_populates="booking",
        lazy="raise",
    )
    handover_records: Mapped[list[object]] = relationship(
        "HandoverRecord",
        foreign_keys="HandoverRecord.booking_id",
        back_populates="booking",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return (
            f"<Booking id={self.id} asset_id={self.asset_id} "
            f"renter_id={self.renter_id} status={self.status.value}>"
        )
