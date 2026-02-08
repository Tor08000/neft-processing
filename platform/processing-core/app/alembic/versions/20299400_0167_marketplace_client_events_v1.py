"""Marketplace client events v1.

Revision ID: 20299400_0167_marketplace_client_events_v1
Revises: 20299380_0166_marketplace_orders_nullable_legacy_fields
Create Date: 2025-02-20 00:00:02.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.types import GUID


revision = "20299400_0167_marketplace_client_events_v1"
down_revision = "20299380_0166_marketplace_orders_nullable_legacy_fields"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(
        bind,
        "marketplace_client_event_type",
        [
            "marketplace.offer_viewed",
            "marketplace.offer_clicked",
            "marketplace.search_performed",
            "marketplace.order_created",
            "marketplace.order_paid",
            "marketplace.order_canceled",
            "marketplace.product_viewed",
            "marketplace.service_viewed",
            "marketplace.filters_changed",
            "marketplace.checkout_started",
        ],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_client_entity_type",
        ["OFFER", "PRODUCT", "SERVICE", "ORDER", "NONE"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_client_event_source",
        ["client_portal", "web", "mobile", "api"],
        schema=DB_SCHEMA,
    )

    event_type_enum = safe_enum(
        bind,
        "marketplace_client_event_type",
        [
            "marketplace.offer_viewed",
            "marketplace.offer_clicked",
            "marketplace.search_performed",
            "marketplace.order_created",
            "marketplace.order_paid",
            "marketplace.order_canceled",
            "marketplace.product_viewed",
            "marketplace.service_viewed",
            "marketplace.filters_changed",
            "marketplace.checkout_started",
        ],
        schema=DB_SCHEMA,
    )
    entity_type_enum = safe_enum(
        bind,
        "marketplace_client_entity_type",
        ["OFFER", "PRODUCT", "SERVICE", "ORDER", "NONE"],
        schema=DB_SCHEMA,
    )
    source_enum = safe_enum(
        bind,
        "marketplace_client_event_source",
        ["client_portal", "web", "mobile", "api"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_client_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("client_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_id", GUID(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("user_id", GUID(), nullable=True),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("event_type", event_type_enum, nullable=False),
        sa.Column("entity_type", entity_type_enum, nullable=False),
        sa.Column("entity_id", GUID(), nullable=True),
        sa.Column("source", source_enum, nullable=False),
        sa.Column("page", sa.Text(), nullable=True),
        sa.Column("utm", JSON_TYPE, nullable=True),
        sa.Column("payload", JSON_TYPE, nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        schema=DB_SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_marketplace_client_events_client_ts",
        "marketplace_client_events",
        ["client_id", "ts"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_client_events_event_ts",
        "marketplace_client_events",
        ["event_type", "ts"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_client_events_entity_ts",
        "marketplace_client_events",
        ["entity_type", "entity_id", "ts"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    pass
