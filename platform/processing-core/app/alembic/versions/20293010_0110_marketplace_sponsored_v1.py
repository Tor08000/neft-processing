"""Marketplace sponsored campaigns v1.

Revision ID: 20293010_0110_marketplace_sponsored_v1
Revises: 20293000_0109_marketplace_partner_subscriptions_analytics_v1
Create Date: 2026-03-01 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import (
    DB_SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_expr_index_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)
from db.types import GUID


revision = "20293010_0110_marketplace_sponsored_v1"
down_revision = "20293000_0109_marketplace_partner_subscriptions_analytics_v1"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(
        bind,
        "sponsored_campaign_status",
        ["DRAFT", "ACTIVE", "PAUSED", "ENDED", "EXHAUSTED"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "sponsored_campaign_objective",
        ["CPC", "CPA"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "sponsored_event_type",
        ["IMPRESSION", "CLICK", "CONVERSION"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "sponsored_spend_type",
        ["CPC_CLICK", "CPA_ORDER"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "sponsored_spend_direction",
        ["DEBIT", "CREDIT"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "sponsored_campaigns",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "sponsored_campaign_status",
                ["DRAFT", "ACTIVE", "PAUSED", "ENDED", "EXHAUSTED"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column(
            "objective",
            safe_enum(
                bind,
                "sponsored_campaign_objective",
                ["CPC", "CPA"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("currency", sa.Text(), nullable=False, server_default="RUB"),
        sa.Column("targeting", JSON_TYPE, nullable=False),
        sa.Column("scope", JSON_TYPE, nullable=False),
        sa.Column("bid", sa.Numeric(18, 4), nullable=False),
        sa.Column("daily_cap", sa.Numeric(18, 4), nullable=True),
        sa.Column("total_budget", sa.Numeric(18, 4), nullable=False),
        sa.Column("spent_budget", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_sponsored_campaigns_active",
        "sponsored_campaigns",
        ["status", "starts_at", "ends_at"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_sponsored_campaigns_partner",
        "sponsored_campaigns",
        ["partner_id", "status"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "sponsored_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("campaign_id", GUID(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("client_id", GUID(), nullable=True),
        sa.Column("user_id", GUID(), nullable=True),
        sa.Column("product_id", GUID(), nullable=True),
        sa.Column(
            "event_type",
            safe_enum(
                bind,
                "sponsored_event_type",
                ["IMPRESSION", "CLICK", "CONVERSION"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("event_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("context", JSON_TYPE, nullable=False),
        sa.Column("meta", JSON_TYPE, nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_sponsored_events_campaign_ts",
        "sponsored_events",
        ["campaign_id", "event_ts"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_sponsored_events_type_ts",
        "sponsored_events",
        ["event_type", "event_ts"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "sponsored_spend_ledger",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("campaign_id", GUID(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column(
            "spend_type",
            safe_enum(
                bind,
                "sponsored_spend_type",
                ["CPC_CLICK", "CPA_ORDER"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("ref_type", sa.Text(), nullable=False),
        sa.Column("ref_id", GUID(), nullable=False),
        sa.Column(
            "direction",
            safe_enum(
                bind,
                "sponsored_spend_direction",
                ["DEBIT", "CREDIT"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
            server_default="DEBIT",
        ),
        sa.Column("reversal_of", GUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_unique_expr_index_if_not_exists(
        bind,
        "ux_sponsored_debit_per_order",
        "sponsored_spend_ledger",
        "(spend_type, ref_id, direction) WHERE direction = 'DEBIT'",
        schema=DB_SCHEMA,
    )
    create_unique_expr_index_if_not_exists(
        bind,
        "ux_sponsored_credit_per_order",
        "sponsored_spend_ledger",
        "(spend_type, ref_id, direction) WHERE direction = 'CREDIT'",
        schema=DB_SCHEMA,
    )
    create_unique_expr_index_if_not_exists(
        bind,
        "ux_sponsored_reversal_of",
        "sponsored_spend_ledger",
        "(reversal_of) WHERE reversal_of IS NOT NULL",
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    pass
