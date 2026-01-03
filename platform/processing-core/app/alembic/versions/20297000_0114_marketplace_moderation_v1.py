"""Marketplace moderation workflow v1.

Revision ID: 20297000_0114_marketplace_moderation_v1
Revises: 20296000_0113_service_completion_proofs_v1
Create Date: 2026-03-10 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from app.alembic.helpers import DB_SCHEMA, column_exists, create_index_if_not_exists, ensure_pg_enum, safe_enum, table_exists
from app.db.types import GUID


revision = "20297000_0114_marketplace_moderation_v1"
down_revision = "20296000_0113_service_completion_proofs_v1"
branch_labels = None
depends_on = None


MODERATION_STATUSES = ["DRAFT", "PENDING_REVIEW", "APPROVED", "REJECTED"]


def _schema_prefix() -> str:
    return f"{DB_SCHEMA}." if DB_SCHEMA else ""


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "marketplace_product_moderation_status", MODERATION_STATUSES, schema=DB_SCHEMA)

    if table_exists(bind, "marketplace_products", schema=DB_SCHEMA):
        if not column_exists(bind, "marketplace_products", "moderation_status", schema=DB_SCHEMA):
            op.add_column(
                "marketplace_products",
                sa.Column(
                    "moderation_status",
                    safe_enum(
                        bind,
                        "marketplace_product_moderation_status",
                        MODERATION_STATUSES,
                        schema=DB_SCHEMA,
                    ),
                    nullable=False,
                    server_default=sa.text("'DRAFT'"),
                ),
                schema=DB_SCHEMA,
            )
        if not column_exists(bind, "marketplace_products", "moderation_reason", schema=DB_SCHEMA):
            op.add_column("marketplace_products", sa.Column("moderation_reason", sa.Text(), nullable=True), schema=DB_SCHEMA)
        if not column_exists(bind, "marketplace_products", "moderated_by", schema=DB_SCHEMA):
            op.add_column("marketplace_products", sa.Column("moderated_by", GUID(), nullable=True), schema=DB_SCHEMA)
        if not column_exists(bind, "marketplace_products", "moderated_at", schema=DB_SCHEMA):
            op.add_column(
                "marketplace_products",
                sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
                schema=DB_SCHEMA,
            )

        op.execute(
            sa.text(
                f"""
                UPDATE {_schema_prefix()}marketplace_products
                SET moderation_status = 'APPROVED'
                WHERE status = 'PUBLISHED' AND moderation_status = 'DRAFT'
                """
            )
        )

        create_index_if_not_exists(
            bind,
            "ix_marketplace_products_moderation_status",
            "marketplace_products",
            ["moderation_status"],
            schema=DB_SCHEMA,
        )


def downgrade() -> None:
    # No downgrade operations for additive changes.
    pass
