"""Marketplace recommendations v1.

Revision ID: 20292020_0109_marketplace_recommendations_v1
Revises: 20292010_0108_marketplace_orders_v1
Create Date: 2026-02-15 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import (
    DB_SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)
from db.types import GUID

revision = "20292020_0109_marketplace_recommendations_v1"
down_revision = "20292010_0108_marketplace_orders_v1"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(
        bind,
        "marketplace_event_type",
        ["VIEW", "CLICK", "ADD_TO_CART", "PURCHASE", "REFUND"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=True),
        sa.Column("client_id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=True),
        sa.Column("partner_id", GUID(), nullable=True),
        sa.Column("product_id", GUID(), nullable=True),
        sa.Column(
            "event_type",
            safe_enum(
                bind,
                "marketplace_event_type",
                ["VIEW", "CLICK", "ADD_TO_CART", "PURCHASE", "REFUND"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("event_ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("context", JSON_TYPE, nullable=True),
        sa.Column("meta", JSON_TYPE, nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_events_client_ts",
        "marketplace_events",
        ["client_id", "event_ts"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_events_product_ts",
        "marketplace_events",
        ["product_id", "event_ts"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_events_partner_ts",
        "marketplace_events",
        ["partner_id", "event_ts"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_events_context_gin",
        "marketplace_events",
        ["context"],
        schema=DB_SCHEMA,
        postgresql_using="gin",
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_events_meta_gin",
        "marketplace_events",
        ["meta"],
        schema=DB_SCHEMA,
        postgresql_using="gin",
    )

    create_table_if_not_exists(
        bind,
        "client_behavior_profiles",
        sa.Column("tenant_id", GUID(), nullable=True),
        sa.Column("client_id", GUID(), primary_key=True),
        sa.Column("period_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("fuel_mix", JSON_TYPE, nullable=True),
        sa.Column("avg_fuel_txn_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("fuel_txn_count", sa.Integer(), nullable=True),
        sa.Column("fuel_txn_days_active", sa.Integer(), nullable=True),
        sa.Column("geo_regions", JSON_TYPE, nullable=True),
        sa.Column("fleet_type", sa.Text(), nullable=True),
        sa.Column("aggressiveness_score", sa.Numeric(6, 4), nullable=True),
        sa.Column("maintenance_risk_score", sa.Numeric(6, 4), nullable=True),
        sa.Column("economy_score", sa.Numeric(6, 4), nullable=True),
        sa.Column("marketplace_affinity", JSON_TYPE, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_client_behavior_profiles_tenant",
        "client_behavior_profiles",
        ["tenant_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "product_taxonomy",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("category_code", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("parent_code", sa.Text(), nullable=True),
        sa.Column("tags", JSON_TYPE, nullable=True),
        schema=DB_SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_product_taxonomy_category",
        "product_taxonomy",
        ["category_code"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "product_attributes",
        sa.Column("product_id", GUID(), primary_key=True),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("category_code", sa.Text(), nullable=False),
        sa.Column("tags", JSON_TYPE, nullable=True),
        sa.Column("compatibility", JSON_TYPE, nullable=True),
        sa.Column("meta", JSON_TYPE, nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_product_attributes_partner",
        "product_attributes",
        ["partner_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_product_attributes_category",
        "product_attributes",
        ["category_code"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "offer_candidates",
        sa.Column("tenant_id", GUID(), nullable=True),
        sa.Column("client_id", GUID(), primary_key=True),
        sa.Column("product_id", GUID(), primary_key=True),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("base_score", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("reasons", JSON_TYPE, nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_offer_candidates_client",
        "offer_candidates",
        ["client_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_offer_candidates_product",
        "offer_candidates",
        ["product_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_offer_candidates_partner",
        "offer_candidates",
        ["partner_id"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    # No downgrade operations for additive changes.
    pass
