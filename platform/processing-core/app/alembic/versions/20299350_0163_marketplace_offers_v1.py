"""Marketplace offers v1.

Revision ID: 20299350_0163_marketplace_offers_v1
Revises: 20299340_0162_marketplace_services_v1
Create Date: 2026-02-17 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import (
    DB_SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)
from db.types import GUID

revision = "20299350_0163_marketplace_offers_v1"
down_revision = "20299340_0162_marketplace_services_v1"
branch_labels = None
depends_on = None

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(
        bind,
        "marketplace_offer_subject_type",
        ["PRODUCT", "SERVICE"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_offer_status",
        ["DRAFT", "PENDING_REVIEW", "ACTIVE", "SUSPENDED", "ARCHIVED"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_offer_price_model",
        ["FIXED", "RANGE", "PER_UNIT", "PER_SERVICE"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_offer_geo_scope",
        ["ALL_PARTNER_LOCATIONS", "SELECTED_LOCATIONS", "REGION"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_offer_entitlement_scope",
        ["ALL_CLIENTS", "SUBSCRIPTION_ONLY", "SEGMENT_ONLY"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_offers",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column(
            "subject_type",
            safe_enum(
                bind,
                "marketplace_offer_subject_type",
                ["PRODUCT", "SERVICE"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("subject_id", GUID(), nullable=False),
        sa.Column("title_override", sa.Text(), nullable=True),
        sa.Column("description_override", sa.Text(), nullable=True),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "marketplace_offer_status",
                ["DRAFT", "PENDING_REVIEW", "ACTIVE", "SUSPENDED", "ARCHIVED"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("moderation_comment", sa.Text(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column(
            "price_model",
            safe_enum(
                bind,
                "marketplace_offer_price_model",
                ["FIXED", "RANGE", "PER_UNIT", "PER_SERVICE"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("price_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("terms", JSON_TYPE, nullable=False),
        sa.Column(
            "geo_scope",
            safe_enum(
                bind,
                "marketplace_offer_geo_scope",
                ["ALL_PARTNER_LOCATIONS", "SELECTED_LOCATIONS", "REGION"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("location_ids", JSON_TYPE, nullable=False),
        sa.Column("region_code", sa.Text(), nullable=True),
        sa.Column(
            "entitlement_scope",
            safe_enum(
                bind,
                "marketplace_offer_entitlement_scope",
                ["ALL_CLIENTS", "SUBSCRIPTION_ONLY", "SEGMENT_ONLY"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("allowed_subscription_codes", JSON_TYPE, nullable=False),
        sa.Column("allowed_client_ids", JSON_TYPE, nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_offers_partner_status",
        "marketplace_offers",
        ["partner_id", "status"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_offers_subject",
        "marketplace_offers",
        ["subject_type", "subject_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_offers_status_validity",
        "marketplace_offers",
        ["status", "valid_from", "valid_to"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_offers_terms_gin",
        "marketplace_offers",
        ["terms"],
        postgresql_using="gin",
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    raise RuntimeError("downgrade_not_supported")
