"""Marketplace catalog v1.

Revision ID: 20292000_0107_marketplace_catalog_v1
Revises: 20291980_0106_fuel_provider_integrations_v1
Create Date: 2026-02-01 00:00:00.000000
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
    is_postgres,
    safe_enum,
)
from db.types import GUID


revision = "20292000_0107_marketplace_catalog_v1"
down_revision = "20291980_0106_fuel_provider_integrations_v1"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def _schema_prefix() -> str:
    return f"{DB_SCHEMA}." if DB_SCHEMA else ""


def _create_worm_delete_trigger(table_name: str) -> None:
    if not is_postgres(op.get_bind()):
        return
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {_schema_prefix()}{table_name}_worm_delete_guard()
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
            FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}{table_name}_worm_delete_guard()
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(
        bind,
        "partner_verification_status",
        ["PENDING", "VERIFIED", "REJECTED"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_product_type",
        ["SERVICE", "PRODUCT"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_price_model",
        ["FIXED", "PER_UNIT", "TIERED"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_product_status",
        ["DRAFT", "PUBLISHED", "ARCHIVED"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_partner_profiles",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "verification_status",
            safe_enum(
                bind,
                "partner_verification_status",
                ["PENDING", "VERIFIED", "REJECTED"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("rating", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_event_id", GUID(), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "uq_marketplace_partner_profiles_partner",
        "marketplace_partner_profiles",
        ["partner_id"],
        unique=True,
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_partner_profiles_verification_status",
        "marketplace_partner_profiles",
        ["verification_status"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_products",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column(
            "type",
            safe_enum(
                bind,
                "marketplace_product_type",
                ["SERVICE", "PRODUCT"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column(
            "price_model",
            safe_enum(
                bind,
                "marketplace_price_model",
                ["FIXED", "PER_UNIT", "TIERED"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("price_config", JSON_TYPE, nullable=False),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "marketplace_product_status",
                ["DRAFT", "PUBLISHED", "ARCHIVED"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_event_id", GUID(), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_products_partner_status",
        "marketplace_products",
        ["partner_id", "status"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_products_status_category",
        "marketplace_products",
        ["status", "category"],
        schema=DB_SCHEMA,
    )

    _create_worm_delete_trigger("marketplace_partner_profiles")
    _create_worm_delete_trigger("marketplace_products")


def downgrade() -> None:
    # No downgrade operations for additive changes.
    pass
