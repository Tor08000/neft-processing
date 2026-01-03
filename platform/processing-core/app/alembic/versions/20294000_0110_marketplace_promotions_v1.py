"""Marketplace promotions v1.

Revision ID: 20294000_0110_marketplace_promotions_v1
Revises: 20293000_0109_marketplace_partner_subscriptions_analytics_v1
Create Date: 2026-02-10 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from app.alembic.helpers import (
    DB_SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    index_exists,
    is_postgres,
    safe_enum,
    table_exists,
    column_exists,
)
from app.db.types import GUID


revision = "20294000_0110_marketplace_promotions_v1"
down_revision = "20293000_0109_marketplace_partner_subscriptions_analytics_v1"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def _schema_prefix() -> str:
    return f"{DB_SCHEMA}." if DB_SCHEMA else ""


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(
        bind,
        "marketplace_promotion_type",
        ["PRODUCT_DISCOUNT", "CATEGORY_DISCOUNT", "PARTNER_STORE_DISCOUNT", "COUPON_PROMO"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_promotion_status",
        ["DRAFT", "ACTIVE", "PAUSED", "ENDED", "ARCHIVED"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_coupon_batch_type",
        ["PUBLIC", "TARGETED"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_coupon_status",
        ["NEW", "ISSUED", "REDEEMED", "EXPIRED", "CANCELED"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_promotions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=True),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column(
            "promo_type",
            safe_enum(
                bind,
                "marketplace_promotion_type",
                ["PRODUCT_DISCOUNT", "CATEGORY_DISCOUNT", "PARTNER_STORE_DISCOUNT", "COUPON_PROMO"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "marketplace_promotion_status",
                ["DRAFT", "ACTIVE", "PAUSED", "ENDED", "ARCHIVED"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scope_json", JSON_TYPE, nullable=False),
        sa.Column("eligibility_json", JSON_TYPE, nullable=True),
        sa.Column("rules_json", JSON_TYPE, nullable=False),
        sa.Column("schedule_json", JSON_TYPE, nullable=True),
        sa.Column("limits_json", JSON_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", GUID(), nullable=True),
        sa.Column("updated_by", GUID(), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_promotions_partner_status",
        "marketplace_promotions",
        ["partner_id", "status"],
        schema=DB_SCHEMA,
    )

    if is_postgres(bind):
        if not index_exists(bind, "ix_marketplace_promotions_status_window", schema=DB_SCHEMA):
            op.execute(
                sa.text(
                    f"""
                    CREATE INDEX ix_marketplace_promotions_status_window
                    ON {_schema_prefix()}marketplace_promotions
                    (status, (schedule_json->>'valid_from'), (schedule_json->>'valid_to'))
                    """
                )
            )
        if not index_exists(bind, "ix_marketplace_promotions_scope_gin", schema=DB_SCHEMA):
            op.execute(
                sa.text(
                    f"""
                    CREATE INDEX ix_marketplace_promotions_scope_gin
                    ON {_schema_prefix()}marketplace_promotions
                    USING gin (scope_json)
                    """
                )
            )

    create_table_if_not_exists(
        bind,
        "marketplace_coupon_batches",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=True),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column(
            "promotion_id",
            GUID(),
            sa.ForeignKey(f"{_schema_prefix()}marketplace_promotions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "batch_type",
            safe_enum(
                bind,
                "marketplace_coupon_batch_type",
                ["PUBLIC", "TARGETED"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("code_prefix", sa.Text(), nullable=True),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("issued_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("redeemed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("meta_json", JSON_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_coupon_batches_partner",
        "marketplace_coupon_batches",
        ["partner_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_coupon_batches_promotion",
        "marketplace_coupon_batches",
        ["promotion_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_coupons",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=True),
        sa.Column(
            "batch_id",
            GUID(),
            sa.ForeignKey(f"{_schema_prefix()}marketplace_coupon_batches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "promotion_id",
            GUID(),
            sa.ForeignKey(f"{_schema_prefix()}marketplace_promotions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "marketplace_coupon_status",
                ["NEW", "ISSUED", "REDEEMED", "EXPIRED", "CANCELED"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("client_id", GUID(), nullable=True),
        sa.Column("redeemed_order_id", GUID(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ux_marketplace_coupons_code",
        "marketplace_coupons",
        ["code"],
        schema=DB_SCHEMA,
        unique=True,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_coupons_client_status",
        "marketplace_coupons",
        ["client_id", "status"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_coupons_promotion_status",
        "marketplace_coupons",
        ["promotion_id", "status"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_promotion_applications",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=True),
        sa.Column(
            "order_id",
            GUID(),
            sa.ForeignKey(f"{_schema_prefix()}marketplace_orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("client_id", GUID(), nullable=False),
        sa.Column(
            "promotion_id",
            GUID(),
            sa.ForeignKey(f"{_schema_prefix()}marketplace_promotions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "coupon_id",
            GUID(),
            sa.ForeignKey(f"{_schema_prefix()}marketplace_coupons.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("applied_discount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("price_snapshot_json", JSON_TYPE, nullable=False),
        sa.Column("decision_json", JSON_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_promotion_applications_order",
        "marketplace_promotion_applications",
        ["order_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_promotion_applications_partner_created",
        "marketplace_promotion_applications",
        ["partner_id", "created_at"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_promotion_applications_client_created",
        "marketplace_promotion_applications",
        ["client_id", "created_at"],
        schema=DB_SCHEMA,
    )

    if table_exists(bind, "marketplace_orders", schema=DB_SCHEMA):
        if not column_exists(bind, "marketplace_orders", "price_snapshot_json", schema=DB_SCHEMA):
            op.add_column("marketplace_orders", sa.Column("price_snapshot_json", JSON_TYPE, nullable=True), schema=DB_SCHEMA)
        if not column_exists(bind, "marketplace_orders", "pricing_version", schema=DB_SCHEMA):
            op.add_column("marketplace_orders", sa.Column("pricing_version", sa.Text(), nullable=True), schema=DB_SCHEMA)
        if not column_exists(bind, "marketplace_orders", "applied_promotions_json", schema=DB_SCHEMA):
            op.add_column(
                "marketplace_orders", sa.Column("applied_promotions_json", JSON_TYPE, nullable=True), schema=DB_SCHEMA
            )
        if not column_exists(bind, "marketplace_orders", "coupon_code_used", schema=DB_SCHEMA):
            op.add_column("marketplace_orders", sa.Column("coupon_code_used", sa.Text(), nullable=True), schema=DB_SCHEMA)


def downgrade() -> None:
    # No downgrade operations for additive changes.
    pass
