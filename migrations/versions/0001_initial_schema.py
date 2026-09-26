"""Initial application schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

renterrole = postgresql.ENUM("renter", "vendor", "admin", name="renterrole", create_type=False)
kycstatus = postgresql.ENUM(
    "pending", "submitted", "verified", "failed", name="kycstatus", create_type=False
)
assetcategory = postgresql.ENUM(
    "camera",
    "lens",
    "lighting",
    "audio",
    "drone",
    "gimbal",
    "other",
    name="assetcategory",
    create_type=False,
)
city = postgresql.ENUM("lagos", "abuja", name="city", create_type=False)
bookingstatus = postgresql.ENUM(
    "pending",
    "confirmed",
    "active",
    "completed",
    "cancelled",
    "disputed",
    name="bookingstatus",
    create_type=False,
)
handoverdirection = postgresql.ENUM("pickup", "return", name="handoverdirection", create_type=False)
handoverstatus = postgresql.ENUM(
    "draft",
    "vendor_signed",
    "renter_signed",
    "completed",
    name="handoverstatus",
    create_type=False,
)
paymenttype = postgresql.ENUM(
    "deposit",
    "rental_balance",
    "payout",
    "refund",
    "protection_waiver",
    name="paymenttype",
    create_type=False,
)
paymentstatus = postgresql.ENUM(
    "pending",
    "authorized",
    "captured",
    "failed",
    "refunded",
    name="paymentstatus",
    create_type=False,
)
depositstatus = postgresql.ENUM(
    "held", "released", "claimed", name="depositstatus", create_type=False
)
payoutstatus = postgresql.ENUM(
    "pending", "eligible", "paid", name="payoutstatus", create_type=False
)

ENUMS = (
    renterrole,
    kycstatus,
    assetcategory,
    city,
    bookingstatus,
    handoverdirection,
    handoverstatus,
    paymenttype,
    paymentstatus,
    depositstatus,
    payoutstatus,
)


def upgrade() -> None:
    """Create the initial application schema."""

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    bind = op.get_bind()
    for enum_type in ENUMS:
        enum_type.create(bind, checkfirst=False)

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("role", renterrole, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("phone"),
    )
    op.create_index("ix_users_phone", "users", ["phone"], unique=False)

    op.create_table(
        "assets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", assetcategory, nullable=False),
        sa.Column("serial_number", sa.String(), nullable=True),
        sa.Column("daily_rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("deposit_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_available", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("city", city, nullable=False),
        sa.Column("condition_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("daily_rate > 0", name="ck_assets_daily_rate_positive"),
        sa.CheckConstraint("deposit_amount >= 0", name="ck_assets_deposit_amount_nonnegative"),
        sa.ForeignKeyConstraint(["vendor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assets_vendor_id", "assets", ["vendor_id"], unique=False)

    op.create_table(
        "kyc_profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_reference", sa.String(), nullable=True),
        sa.Column("status", kycstatus, nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("national_id_type", sa.String(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.CheckConstraint("tier BETWEEN 0 AND 2", name="ck_kyc_profiles_supported_tier"),
        sa.CheckConstraint(
            "status <> 'verified' OR verified_at IS NOT NULL",
            name="ck_kyc_profiles_verified_at_required",
        ),
        sa.CheckConstraint(
            "(status = 'verified' AND verified_at IS NOT NULL AND tier BETWEEN 1 AND 2) OR "
            "(status <> 'verified' AND verified_at IS NULL AND tier = 0)",
            name="ck_kyc_profiles_verification_consistency",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("provider_reference", name="uq_kyc_profiles_provider_reference"),
    )

    op.create_table(
        "availability_windows",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("starts_at", sa.Date(), nullable=False),
        sa.Column("ends_at", sa.Date(), nullable=False),
        sa.Column("is_blocked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("starts_at <= ends_at", name="ck_availability_windows_valid_date_range"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_availability_windows_asset_id", "availability_windows", ["asset_id"], unique=False
    )

    op.create_table(
        "bookings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("renter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("status", bookingstatus, server_default=sa.text("'pending'"), nullable=False),
        sa.Column("total_rental_fee", sa.Numeric(12, 2), nullable=False),
        sa.Column("deposit_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("platform_note", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("deposit_amount >= 0", name="ck_bookings_deposit_amount_nonnegative"),
        sa.CheckConstraint("total_rental_fee > 0", name="ck_bookings_total_rental_fee_positive"),
        sa.CheckConstraint("starts_on <= ends_on", name="ck_bookings_valid_date_range"),
        postgresql.ExcludeConstraint(
            ("asset_id", "="),
            (sa.text("daterange(starts_on, ends_on, '[]')"), "&&"),
            where=sa.text("status IN ('confirmed', 'active')"),
            name="ex_bookings_no_active_asset_overlap",
            using="gist",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["renter_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["vendor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "renter_id", name="uq_bookings_id_renter"),
        sa.UniqueConstraint("id", "vendor_id", name="uq_bookings_id_vendor"),
    )
    op.create_index("ix_bookings_asset_id", "bookings", ["asset_id"], unique=False)
    op.create_index("ix_bookings_renter_id", "bookings", ["renter_id"], unique=False)
    op.create_index("ix_bookings_vendor_id", "bookings", ["vendor_id"], unique=False)

    op.create_table(
        "handover_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction", handoverdirection, nullable=False),
        sa.Column("status", handoverstatus, server_default=sa.text("'draft'"), nullable=False),
        sa.Column("condition_checklist", postgresql.JSONB(), nullable=False),
        sa.Column("vendor_signer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("renter_signer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("vendor_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("renter_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_urls", postgresql.JSONB(), nullable=True),
        sa.Column("location_lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("location_lng", sa.Numeric(9, 6), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status <> 'completed' OR (vendor_signer_id IS NOT NULL AND "
            "renter_signer_id IS NOT NULL AND vendor_signed_at IS NOT NULL AND "
            "renter_signed_at IS NOT NULL AND evidence_urls IS NOT NULL AND "
            "jsonb_typeof(evidence_urls) = 'array' AND jsonb_array_length(evidence_urls) > 0)",
            name="ck_handover_records_completed_requirements",
        ),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"]),
        sa.ForeignKeyConstraint(
            ["booking_id", "vendor_signer_id"],
            ["bookings.id", "bookings.vendor_id"],
            name="fk_handover_records_booking_vendor",
        ),
        sa.ForeignKeyConstraint(
            ["booking_id", "renter_signer_id"],
            ["bookings.id", "bookings.renter_id"],
            name="fk_handover_records_booking_renter",
        ),
        sa.ForeignKeyConstraint(["renter_signer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "booking_id", "direction", name="uq_handover_records_booking_direction"
        ),
    )
    op.create_index(
        "ix_handover_records_booking_id", "handover_records", ["booking_id"], unique=False
    )

    op.create_table(
        "payments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", paymenttype, nullable=False),
        sa.Column("status", paymentstatus, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_reference", sa.String(), nullable=True),
        sa.Column("provider_virtual_account", sa.String(), nullable=True),
        sa.Column("vendor_recipient_code", sa.String(), nullable=True),
        sa.Column("vendor_subaccount_code", sa.String(), nullable=True),
        sa.Column("platform_fee", sa.Numeric(12, 2), nullable=True),
        sa.Column("settlement_reference", sa.String(), nullable=True),
        sa.Column("deposit_status", depositstatus, nullable=True),
        sa.Column("payout_status", payoutstatus, nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deposit_held_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deposit_released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deposit_claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payout_eligible_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        sa.CheckConstraint(
            "type <> 'payout' OR (vendor_recipient_code IS NOT NULL AND platform_fee IS NOT NULL)",
            name="ck_payments_payout_fields_required",
        ),
        sa.CheckConstraint(
            "platform_fee IS NULL OR platform_fee >= 0",
            name="ck_payments_platform_fee_nonnegative",
        ),
        sa.CheckConstraint(
            "(type = 'deposit' AND deposit_status IS NOT NULL) OR "
            "(type <> 'deposit' AND deposit_status IS NULL AND deposit_held_at IS NULL "
            "AND deposit_released_at IS NULL AND deposit_claimed_at IS NULL)",
            name="ck_payments_deposit_lifecycle_type",
        ),
        sa.CheckConstraint(
            "(type = 'payout' AND payout_status IS NOT NULL) OR "
            "(type <> 'payout' AND payout_status IS NULL AND payout_eligible_at IS NULL "
            "AND paid_at IS NULL)",
            name="ck_payments_payout_lifecycle_type",
        ),
        sa.CheckConstraint(
            "deposit_status IS NULL OR (deposit_held_at IS NOT NULL "
            "AND (deposit_status <> 'released' OR deposit_released_at IS NOT NULL) "
            "AND (deposit_status <> 'claimed' OR deposit_claimed_at IS NOT NULL))",
            name="ck_payments_deposit_status_timestamps",
        ),
        sa.CheckConstraint(
            "payout_status IS NULL OR (payout_status = 'pending' OR "
            "payout_eligible_at IS NOT NULL) AND "
            "(payout_status <> 'paid' OR paid_at IS NOT NULL)",
            name="ck_payments_payout_status_timestamps",
        ),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_reference"),
    )
    op.create_index("ix_payments_booking_id", "payments", ["booking_id"], unique=False)


def downgrade() -> None:
    """Remove the initial application schema."""

    op.drop_index("ix_payments_booking_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_handover_records_booking_id", table_name="handover_records")
    op.drop_table("handover_records")
    op.drop_index("ix_bookings_vendor_id", table_name="bookings")
    op.drop_index("ix_bookings_renter_id", table_name="bookings")
    op.drop_index("ix_bookings_asset_id", table_name="bookings")
    op.drop_table("bookings")
    op.drop_index("ix_availability_windows_asset_id", table_name="availability_windows")
    op.drop_table("availability_windows")
    op.drop_table("kyc_profiles")
    op.drop_index("ix_assets_vendor_id", table_name="assets")
    op.drop_table("assets")
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    for enum_type in reversed(ENUMS):
        enum_type.drop(bind, checkfirst=False)

    # Extensions may predate Vouch and be shared by other schemas, so downgrade
    # removes only objects owned by this migration and leaves extensions installed.
