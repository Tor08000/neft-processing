"""Create marketplace adjustments table used by partner trust settlement views.

Revision ID: 20300260_0219_marketplace_adjustments_runtime_repair
Revises: 20300250_0218_otp_challenges_nullable_client_id
Create Date: 2030-01-19 03:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.schema import resolve_db_schema
from db.types import GUID


revision = "20300260_0219_marketplace_adjustments_runtime_repair"
down_revision = "20300250_0218_otp_challenges_nullable_client_id"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

ADJUSTMENT_TYPES = ["PENALTY", "CREDIT_NOTE", "MANUAL_DEBIT", "MANUAL_CREDIT"]
JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "marketplace_adjustment_type", ADJUSTMENT_TYPES, schema=SCHEMA)
    adjustment_type_enum = safe_enum(
        bind, "marketplace_adjustment_type", ADJUSTMENT_TYPES, schema=SCHEMA
    )

    create_table_if_not_exists(
        bind,
        "marketplace_adjustments",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("order_id", GUID(), nullable=True),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("type", adjustment_type_enum, nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("meta", JSON_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_marketplace_adjustments_partner_id",
        "marketplace_adjustments",
        ["partner_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_adjustments_order_id",
        "marketplace_adjustments",
        ["order_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_adjustments_period",
        "marketplace_adjustments",
        ["period"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    pass
