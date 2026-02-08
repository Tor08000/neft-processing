"""Marketplace product cards v1.

Revision ID: 20299330_0161_marketplace_product_cards_v1
Revises: 20299320_0160_clients_indexes_restore
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
    ensure_pg_enum,
    safe_enum,
)
from db.types import GUID


revision = "20299330_0161_marketplace_product_cards_v1"
down_revision = "20299320_0160_clients_indexes_restore"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(
        bind,
        "marketplace_product_card_status",
        ["DRAFT", "PENDING_REVIEW", "ACTIVE", "SUSPENDED", "ARCHIVED"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_product_cards",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "marketplace_product_card_status",
                ["DRAFT", "PENDING_REVIEW", "ACTIVE", "SUSPENDED", "ARCHIVED"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("tags", JSON_TYPE, nullable=False),
        sa.Column("attributes", JSON_TYPE, nullable=False),
        sa.Column("variants", JSON_TYPE, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_product_cards_partner_status",
        "marketplace_product_cards",
        ["partner_id", "status"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_product_cards_status_category",
        "marketplace_product_cards",
        ["status", "category"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_product_media",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("product_id", GUID(), nullable=False),
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
        "ix_marketplace_product_media_product",
        "marketplace_product_media",
        ["product_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "uq_marketplace_product_media_attachment",
        "marketplace_product_media",
        ["product_id", "attachment_id"],
        unique=True,
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    raise RuntimeError("downgrade_not_supported")
