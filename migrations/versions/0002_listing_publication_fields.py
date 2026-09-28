"""Add listing-publication fields to assets table.

Revision ID: 0002_listing_publication_fields
Revises: 0001_initial_schema
Create Date: 2026-09-28

Changes
-------
* New enum type ``listingstatus`` with values draft / review / active / paused / rejected.
* New columns on ``assets``:
  - ``listing_status``       — publication state; default and backfill are ``draft``.
  - ``minimum_trust_tier``   — integer 0-2 with CHECK; default 0.
  - ``review_actor_id``      — nullable FK to ``users.id``; records which admin reviewed.
  - ``reviewed_at``          — nullable TIMESTAMPTZ; timestamp of the review decision.
  - ``review_reason``        — nullable TEXT; reason text for approve / reject / pause.
* Partial index ``ix_assets_public_lagos`` accelerates public Lagos inventory search.
* All existing asset rows are backfilled to ``listing_status = 'draft'`` so they are
  never accidentally published before a manual review.

Rollback removes the new columns, index, and enum type in the correct dependency order.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
# Revision metadata
# ---------------------------------------------------------------------------

revision: str = "0002_listing_publication_fields"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# We create the enum explicitly so it is owned by the migration and can be
# dropped cleanly on downgrade.
listingstatus = postgresql.ENUM(
    "draft",
    "review",
    "active",
    "paused",
    "rejected",
    name="listingstatus",
    create_type=False,
)


def upgrade() -> None:
    # 1. Create the new PostgreSQL enum type.
    listingstatus.create(op.get_bind(), checkfirst=True)

    # 2. Add columns.  listing_status uses USING to convert the server default.
    op.add_column(
        "assets",
        sa.Column(
            "listing_status",
            sa.Enum(
                "draft",
                "review",
                "active",
                "paused",
                "rejected",
                name="listingstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
    )
    op.add_column(
        "assets",
        sa.Column(
            "minimum_trust_tier",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "assets",
        sa.Column(
            "review_actor_id",
            sa.UUID(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "assets",
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "assets",
        sa.Column(
            "review_reason",
            sa.Text(),
            nullable=True,
        ),
    )

    # 3. Backfill: set existing rows explicitly to 'draft' (server_default already
    #    covers new rows; this makes the intent visible in the audit trail).
    op.execute("UPDATE assets SET listing_status = 'draft' WHERE listing_status = 'draft'")

    # 4. Add CHECK constraint for trust tier range.
    op.create_check_constraint(
        "ck_assets_minimum_trust_tier_valid",
        "assets",
        "minimum_trust_tier BETWEEN 0 AND 2",
    )

    # 5. Partial index for fast public Lagos inventory queries.
    op.create_index(
        "ix_assets_public_lagos",
        "assets",
        ["city", "category", "daily_rate", "created_at", "id"],
        postgresql_where=sa.text(
            "listing_status = 'active' AND is_available = true AND deleted_at IS NULL"
        ),
    )


def downgrade() -> None:
    # Reverse order: index → constraint → columns → enum.
    op.drop_index("ix_assets_public_lagos", table_name="assets")
    op.drop_constraint("ck_assets_minimum_trust_tier_valid", "assets", type_="check")
    op.drop_column("assets", "review_reason")
    op.drop_column("assets", "reviewed_at")
    op.drop_column("assets", "review_actor_id")
    op.drop_column("assets", "minimum_trust_tier")
    op.drop_column("assets", "listing_status")
    listingstatus.drop(op.get_bind(), checkfirst=True)
