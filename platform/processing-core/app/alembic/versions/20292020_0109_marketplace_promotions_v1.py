"""Marketplace promotions and gamification v1.

Revision ID: 20292020_0109_marketplace_promotions_v1
Revises: 20292010_0108_marketplace_orders_v1
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
    is_postgres,
    safe_enum,
)
from app.db.types import GUID


revision = "20292020_0109_marketplace_promotions_v1"
down_revision = "20292010_0108_marketplace_orders_v1"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def _schema_prefix() -> str:
    return f"{DB_SCHEMA}." if DB_SCHEMA else ""


def _create_worm_guard(table_name: str) -> None:
    if not is_postgres(op.get_bind()):
        return
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {_schema_prefix()}{table_name}_worm_guard()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION '{table_name} is WORM';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            DROP TRIGGER IF EXISTS {table_name}_worm_update
            ON {_schema_prefix()}{table_name}
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {table_name}_worm_update
            BEFORE UPDATE ON {_schema_prefix()}{table_name}
            FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}{table_name}_worm_guard()
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            DROP TRIGGER IF EXISTS {table_name}_worm_delete
            ON {_schema_prefix()}{table_name}
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {table_name}_worm_delete
            BEFORE DELETE ON {_schema_prefix()}{table_name}
            FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}{table_name}_worm_guard()
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(
        bind,
        "promotion_type",
        [
            "PRODUCT_DISCOUNT",
            "CATEGORY_DISCOUNT",
            "BUNDLE_DISCOUNT",
            "TIER_DISCOUNT",
            "PUBLIC_COUPON",
            "TARGETED_COUPON",
            "AUTO_COUPON",
            "FLASH_SALE",
            "HAPPY_HOURS",
            "SPONSORED_PLACEMENT",
        ],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "promotion_status",
        ["DRAFT", "ACTIVE", "PAUSED", "ENDED", "ARCHIVED"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "coupon_status",
        ["NEW", "ISSUED", "REDEEMED", "EXPIRED", "CANCELED"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "promo_budget_model",
        ["CPA", "CPC"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "promo_budget_status",
        ["ACTIVE", "PAUSED", "EXHAUSTED"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "partner_mission_status",
        ["ACTIVE", "COMPLETED", "CLAIMED", "EXPIRED"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "promotions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column(
            "promo_type",
            safe_enum(
                bind,
                "promotion_type",
                [
                    "PRODUCT_DISCOUNT",
                    "CATEGORY_DISCOUNT",
                    "BUNDLE_DISCOUNT",
                    "TIER_DISCOUNT",
                    "PUBLIC_COUPON",
                    "TARGETED_COUPON",
                    "AUTO_COUPON",
                    "FLASH_SALE",
                    "HAPPY_HOURS",
                    "SPONSORED_PLACEMENT",
                ],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "promotion_status",
                ["DRAFT", "ACTIVE", "PAUSED", "ENDED", "ARCHIVED"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scope", JSON_TYPE, nullable=False),
        sa.Column("eligibility", JSON_TYPE, nullable=False),
        sa.Column("rules", JSON_TYPE, nullable=False),
        sa.Column("budget", JSON_TYPE, nullable=True),
        sa.Column("limits", JSON_TYPE, nullable=True),
        sa.Column("schedule", JSON_TYPE, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_event_id", GUID(), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_promotions_partner_status",
        "promotions",
        ["partner_id", "status"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "coupon_batches",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("promotion_id", GUID(), nullable=False),
        sa.Column("code_prefix", sa.Text(), nullable=True),
        sa.Column("total_count", sa.Numeric(18, 0), nullable=True),
        sa.Column("issued_count", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("redeemed_count", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["promotion_id"],
            [f"{_schema_prefix()}promotions.id"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_coupon_batches_partner_promo",
        "coupon_batches",
        ["partner_id", "promotion_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "coupons",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("batch_id", GUID(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "coupon_status",
                ["NEW", "ISSUED", "REDEEMED", "EXPIRED", "CANCELED"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("client_id", GUID(), nullable=True),
        sa.Column("redeemed_order_id", GUID(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            [f"{_schema_prefix()}coupon_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("code", name="uq_coupons_code"),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_coupons_batch_status",
        "coupons",
        ["batch_id", "status"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "promo_budgets",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("promotion_id", GUID(), nullable=False),
        sa.Column(
            "model",
            safe_enum(bind, "promo_budget_model", ["CPA", "CPC"], schema=DB_SCHEMA),
            nullable=False,
        ),
        sa.Column("currency", sa.Text(), nullable=False, server_default="RUB"),
        sa.Column("total_budget", sa.Numeric(18, 2), nullable=False),
        sa.Column("spent_budget", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("max_bid", sa.Numeric(18, 2), nullable=False),
        sa.Column("daily_cap", sa.Numeric(18, 2), nullable=True),
        sa.Column(
            "status",
            safe_enum(bind, "promo_budget_status", ["ACTIVE", "PAUSED", "EXHAUSTED"], schema=DB_SCHEMA),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["promotion_id"],
            [f"{_schema_prefix()}promotions.id"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_promo_budgets_promotion",
        "promo_budgets",
        ["promotion_id", "status"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "promotion_applications",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("promotion_id", GUID(), nullable=False),
        sa.Column("order_id", GUID(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("client_id", GUID(), nullable=False),
        sa.Column("applied_discount", sa.Numeric(18, 2), nullable=False),
        sa.Column("applied_reason", JSON_TYPE, nullable=False),
        sa.Column("final_price_snapshot", JSON_TYPE, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("audit_event_id", GUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["promotion_id"],
            [f"{_schema_prefix()}promotions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            [f"{_schema_prefix()}marketplace_orders.id"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_promo_apps_order",
        "promotion_applications",
        ["order_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_tiers",
        sa.Column("tier_code", sa.Text(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("benefits", JSON_TYPE, nullable=False),
        sa.Column("thresholds", JSON_TYPE, nullable=False),
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_tier_state",
        sa.Column("partner_id", GUID(), primary_key=True),
        sa.Column("tier_code", sa.Text(), nullable=False),
        sa.Column("score", sa.Numeric(18, 2), nullable=False),
        sa.Column("metrics_snapshot", JSON_TYPE, nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tier_code"],
            [f"{_schema_prefix()}partner_tiers.tier_code"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_missions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rule", JSON_TYPE, nullable=False),
        sa.Column("reward", JSON_TYPE, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_mission_progress",
        sa.Column("partner_id", GUID(), primary_key=True),
        sa.Column("mission_id", GUID(), primary_key=True),
        sa.Column("progress", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "partner_mission_status",
                ["ACTIVE", "COMPLETED", "CLAIMED", "EXPIRED"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["mission_id"],
            [f"{_schema_prefix()}partner_missions.id"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_badges",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.Text(), nullable=True),
        sa.Column("rule", JSON_TYPE, nullable=False),
        sa.UniqueConstraint("code", name="uq_partner_badges_code"),
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_badge_awards",
        sa.Column("partner_id", GUID(), primary_key=True),
        sa.Column("badge_id", GUID(), primary_key=True),
        sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["badge_id"],
            [f"{_schema_prefix()}partner_badges.id"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )

    _create_worm_guard("promotion_applications")


def downgrade() -> None:
    # No downgrade operations for additive changes.
    pass
