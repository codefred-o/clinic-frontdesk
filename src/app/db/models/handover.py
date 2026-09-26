"""HandoverRecord ORM model for rental item pickup and return handovers."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class HandoverDirection(enum.StrEnum):
    pickup = "pickup"
    return_ = "return"


class HandoverStatus(enum.StrEnum):
    draft = "draft"
    vendor_signed = "vendor_signed"
    renter_signed = "renter_signed"
    completed = "completed"


class HandoverRecord(TimestampMixin, Base):
    __tablename__ = "handover_records"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id"),
        nullable=False,
        index=True,
    )
    direction: Mapped[HandoverDirection] = mapped_column(
        Enum(HandoverDirection, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    status: Mapped[HandoverStatus] = mapped_column(
        Enum(HandoverStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=HandoverStatus.draft,
        server_default=HandoverStatus.draft.value,
    )
    condition_checklist: Mapped[dict] = mapped_column(JSONB, nullable=False)
    vendor_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    renter_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    evidence_urls: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    location_lat: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    location_lng: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    booking: Mapped[Booking] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Booking",
        back_populates="handover_records",
        lazy="raise",
    )

    __table_args__ = (Index("ix_handover_records_booking_id", "booking_id"),)

    def __repr__(self) -> str:
        return (
            f"<HandoverRecord id={self.id!r} booking_id={self.booking_id!r} "
            f"direction={self.direction!r} status={self.status!r}>"
        )
