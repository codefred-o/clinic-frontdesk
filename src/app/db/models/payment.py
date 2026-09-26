"""Payment ORM model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class PaymentType(enum.StrEnum):
    deposit = "deposit"
    rental_balance = "rental_balance"
    payout = "payout"
    refund = "refund"
    protection_waiver = "protection_waiver"


class PaymentStatus(enum.StrEnum):
    pending = "pending"
    authorized = "authorized"
    captured = "captured"
    failed = "failed"
    refunded = "refunded"


class Payment(TimestampMixin, Base):
    """Represents a financial transaction tied to a booking."""

    __tablename__ = "payments"
    __table_args__ = (Index("ix_payments_booking_id", "booking_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id"),
        nullable=False,
    )
    type: Mapped[PaymentType] = mapped_column(Enum(PaymentType, name="paymenttype"), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="paymentstatus"), default=PaymentStatus.pending
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String, default="NGN")
    provider: Mapped[str] = mapped_column(String, default="paystack")
    provider_reference: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    provider_virtual_account: Mapped[str | None] = mapped_column(String, nullable=True)
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column(JSONB, name="metadata", nullable=True)

    booking: Mapped[Booking] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="payments",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return (
            f"<Payment id={self.id!s} type={self.type.value} "
            f"status={self.status.value} amount={self.amount} {self.currency}>"
        )
