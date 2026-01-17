"""Allow usage meter pricing in catalog.

Revision ID: 20299160_0146_pricing_catalog_usage_meter
Revises: 20299150_0145_service_slo_framework
Create Date: 2026-02-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

from alembic_helpers import DB_SCHEMA


revision = "20299160_0146_pricing_catalog_usage_meter"
down_revision = "20299150_0145_service_slo_framework"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema_prefix = f"{DB_SCHEMA}." if DB_SCHEMA else ""
    op.execute(
        f"""
        ALTER TABLE {schema_prefix}pricing_catalog
        DROP CONSTRAINT IF EXISTS pricing_catalog_item_type_check;
        """
    )
    op.execute(
        f"""
        ALTER TABLE {schema_prefix}pricing_catalog
        ADD CONSTRAINT pricing_catalog_item_type_check
        CHECK (item_type IN ('PLAN', 'ADDON', 'USAGE_METER'));
        """
    )


def downgrade() -> None:
    schema_prefix = f"{DB_SCHEMA}." if DB_SCHEMA else ""
    op.execute(
        f"""
        ALTER TABLE {schema_prefix}pricing_catalog
        DROP CONSTRAINT IF EXISTS pricing_catalog_item_type_check;
        """
    )
    op.execute(
        f"""
        ALTER TABLE {schema_prefix}pricing_catalog
        ADD CONSTRAINT pricing_catalog_item_type_check
        CHECK (item_type IN ('PLAN', 'ADDON'));
        """
    )
