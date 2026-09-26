"""ORM models for users and KYC profiles."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    pass


class RenterRole(enum.StrEnum):
    renter = "renter"
    vendor = "vendor"
    admin = "admin"


class KYCStatus(enum.StrEnum):
    pending = "pending"
    submitted = "submitted"
    verified = "verified"
    failed = "failed"


class User(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_phone", "phone"),)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    phone: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    role: Mapped[RenterRole] = mapped_column(
        Enum(RenterRole, name="renterrole"),
        nullable=False,
        default=RenterRole.renter,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    kyc_profile: Mapped[KYCProfile | None] = relationship(
        "KYCProfile",
        back_populates="user",
        uselist=False,
        lazy="raise",
    )
    assets: Mapped[list] = relationship(
        "Asset",
        back_populates="vendor",
        lazy="raise",
    )
    bookings_as_renter: Mapped[list] = relationship(
        "Booking",
        back_populates="renter",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} phone={self.phone!r} role={self.role.value!r}>"


class KYCProfile(TimestampMixin, Base):
    __tablename__ = "kyc_profiles"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[KYCStatus] = mapped_column(
        Enum(KYCStatus, name="kycstatus"),
        nullable=False,
        default=KYCStatus.pending,
    )
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    national_id_type: Mapped[str | None] = mapped_column(String, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="kyc_profile",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<KYCProfile id={self.id} user_id={self.user_id} status={self.status.value!r}>"
