"""Pricing versions, schedules, and subscription entitlements core tables.

Revision ID: 20297210_0126_pricing_versions_v1
Revises: 20297170_0125_legal_docs_registry
Create Date: 2029-09-10 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import (
    SCHEMA,
    column_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    ensure_pg_enum_value,
    table_exists,
)


revision = "20297210_0126_pricing_versions_v1"
down_revision = "20297170_0125_legal_docs_registry"
branch_labels = None
depends_on = None


PRICE_VERSION_STATUS = ["DRAFT", "PUBLISHED", "ACTIVE", "ROLLED_BACK", "ARCHIVED"]
PRICE_SCHEDULE_STATUS = ["SCHEDULED", "ACTIVE", "EXPIRED", "CANCELLED"]
SUBSCRIPTION_EVENT_TYPE = [
    "ASSIGNED",
    "UPGRADED",
    "DOWNGRADED",
    "RENEWED",
    "CANCELLED",
    "PRORATED",
    "PRICE_VERSION_CHANGED",
]
SUBSCRIPTION_MODULE_CODES = ["BILLING", "DOCS", "FLEET", "CRM"]

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "price_version_status", PRICE_VERSION_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "price_schedule_status", PRICE_SCHEDULE_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "subscription_event_type", SUBSCRIPTION_EVENT_TYPE, schema=SCHEMA)
    for value in SUBSCRIPTION_MODULE_CODES:
        ensure_pg_enum_value(bind, "subscription_module_code", value, schema=SCHEMA)

    if table_exists(bind, "client_subscriptions", schema=SCHEMA):
        if not column_exists(bind, "client_subscriptions", "billing_anchor_day", schema=SCHEMA):
            op.add_column(
                "client_subscriptions",
                sa.Column("billing_anchor_day", sa.Integer, nullable=False, server_default="1"),
                schema=SCHEMA,
            )
        if not column_exists(bind, "client_subscriptions", "current_price_version_id", schema=SCHEMA):
            op.add_column(
                "client_subscriptions",
                sa.Column("current_price_version_id", sa.String(36), nullable=True),
                schema=SCHEMA,
            )

    create_table_if_not_exists(
        bind,
        "subscription_plan_limits",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("plan_id", sa.String(64), sa.ForeignKey(f"{SCHEMA}.subscription_plans.id"), nullable=False),
        sa.Column("limit_code", sa.String(64), nullable=False),
        sa.Column("value_int", sa.BigInteger, nullable=True),
        sa.Column("value_decimal", sa.Numeric(18, 6), nullable=True),
        sa.Column("value_text", sa.String(128), nullable=True),
        sa.Column("value_json", JSON_TYPE, nullable=True),
        sa.Column("period", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("plan_id", "limit_code", "period", name="uq_subscription_plan_limit"),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_subscription_plan_limits_plan_id",
        "subscription_plan_limits",
        ["plan_id"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "subscription_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column(
            "event_type",
            postgresql.ENUM(
                *SUBSCRIPTION_EVENT_TYPE,
                name="subscription_event_type",
                schema=SCHEMA,
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("payload", JSON_TYPE, nullable=True),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_subscription_events_client_id",
        "subscription_events",
        ["client_id"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "subscription_usage_counters",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("counter_code", sa.String(64), nullable=False),
        sa.Column("period_key", sa.String(16), nullable=False),
        sa.Column("value", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("client_id", "counter_code", "period_key", name="uq_subscription_usage"),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_subscription_usage_counters_client_id",
        "subscription_usage_counters",
        ["client_id"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "price_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                *PRICE_VERSION_STATUS,
                name="price_version_status",
                schema=SCHEMA,
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.String(512), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "price_version_items",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("price_version_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.price_versions.id"), nullable=False),
        sa.Column("plan_code", sa.String(64), nullable=False),
        sa.Column("billing_period", sa.String(16), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("base_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("setup_fee", sa.Numeric(18, 6), nullable=True),
        sa.Column("meta", JSON_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "price_version_id",
            "plan_code",
            "billing_period",
            "currency",
            name="uq_price_version_item",
        ),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_price_version_items_version",
        "price_version_items",
        ["price_version_id"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "price_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("price_version_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.price_versions.id"), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "status",
            postgresql.ENUM(
                *PRICE_SCHEDULE_STATUS,
                name="price_schedule_status",
                schema=SCHEMA,
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_price_schedules_version",
        "price_schedules",
        ["price_version_id"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "price_version_audit",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("price_version_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.price_versions.id"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("payload", JSON_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_price_version_audit_version",
        "price_version_audit",
        ["price_version_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    pass
