"""Marketplace services v1.

Revision ID: 20299340_0162_marketplace_services_v1
Revises: 20299330_0161_marketplace_product_cards_v1
Create Date: 2026-02-16 00:00:00.000000
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


revision = "20299340_0162_marketplace_services_v1"
down_revision = "20299330_0161_marketplace_product_cards_v1"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(
        bind,
        "marketplace_service_status",
        ["DRAFT", "PENDING_REVIEW", "ACTIVE", "SUSPENDED", "ARCHIVED"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_services",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "marketplace_service_status",
                ["DRAFT", "PENDING_REVIEW", "ACTIVE", "SUSPENDED", "ARCHIVED"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("tags", JSON_TYPE, nullable=False),
        sa.Column("attributes", JSON_TYPE, nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_services_partner_status_updated",
        "marketplace_services",
        ["partner_id", "status", "updated_at"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_service_media",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("service_id", GUID(), nullable=False),
        sa.Column("attachment_id", GUID(), nullable=False),
        sa.Column("bucket", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("checksum", sa.Text(), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("mime", sa.Text(), nullable=True),
        sa.Column("sort_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_service_media_service",
        "marketplace_service_media",
        ["service_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "uq_marketplace_service_media_attachment",
        "marketplace_service_media",
        ["service_id", "attachment_id"],
        unique=True,
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_service_locations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("service_id", GUID(), nullable=False),
        sa.Column("location_id", GUID(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 6), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_service_locations_service",
        "marketplace_service_locations",
        ["service_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_service_schedule_rules",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("service_location_id", GUID(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("time_from", sa.Text(), nullable=False),
        sa.Column("time_to", sa.Text(), nullable=False),
        sa.Column("slot_duration_min", sa.Integer(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_service_schedule_rules_location_weekday",
        "marketplace_service_schedule_rules",
        ["service_location_id", "weekday"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_service_schedule_exceptions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("service_location_id", GUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("time_from", sa.Text(), nullable=True),
        sa.Column("time_to", sa.Text(), nullable=True),
        sa.Column("capacity_override", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_service_schedule_exceptions_location_date",
        "marketplace_service_schedule_exceptions",
        ["service_location_id", "date"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    raise RuntimeError("downgrade_not_supported")
