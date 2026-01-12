"""Marketplace partner subscriptions and analytics v1.

Revision ID: 20293000_0109_marketplace_partner_subscriptions_analytics_v1
Revises: 20292010_0108_marketplace_orders_v1
Create Date: 2026-01-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import (
    SCHEMA,
    column_exists,
    create_index_if_not_exists,
    ensure_enum_type_exists,
    is_postgres,
    table_exists,
)
from db.types import GUID


revision = "20293000_0109_marketplace_partner_subscriptions_analytics_v1"
down_revision = "20292010_0108_marketplace_orders_v1"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def _schema_prefix() -> str:
    return f"{SCHEMA}." if SCHEMA else ""


def upgrade() -> None:
    bind = op.get_bind()
    ensure_enum_type_exists(
        bind,
        type_name="partner_subscription_status",
        values=["active", "suspended", "canceled"],
        schema=SCHEMA,
    )
    ensure_enum_type_exists(
        bind,
        type_name="partner_subscription_billing_cycle",
        values=["monthly", "yearly"],
        schema=SCHEMA,
    )

    if not table_exists(bind, "partner_plans", schema=SCHEMA):
        op.create_table(
            "partner_plans",
            sa.Column("plan_code", sa.String(length=64), primary_key=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("base_commission", sa.Numeric(5, 2), nullable=False, server_default="0"),
            sa.Column("monthly_fee", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("features", JSON_TYPE, nullable=True),
            sa.Column("limits", JSON_TYPE, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
            schema=SCHEMA,
        )

    if not table_exists(bind, "partner_subscriptions", schema=SCHEMA):
        op.create_table(
            "partner_subscriptions",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("partner_id", GUID(), nullable=False),
            sa.Column(
                "plan_code",
                sa.String(length=64),
                sa.ForeignKey(f"{_schema_prefix()}partner_plans.plan_code"),
                nullable=False,
            ),
            sa.Column(
                "status",
                postgresql.ENUM(
                    "active",
                    "suspended",
                    "canceled",
                    name="partner_subscription_status",
                    schema=SCHEMA,
                    create_type=False,
                ),
                nullable=False,
                server_default="active",
            ),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "billing_cycle",
                postgresql.ENUM(
                    "monthly",
                    "yearly",
                    name="partner_subscription_billing_cycle",
                    schema=SCHEMA,
                    create_type=False,
                ),
                nullable=False,
                server_default="monthly",
            ),
            sa.Column("commission_rate", sa.Numeric(5, 2), nullable=True),
            sa.Column("features", JSON_TYPE, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_partner_subscriptions_partner",
            "partner_subscriptions",
            ["partner_id"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_partner_subscriptions_plan",
            "partner_subscriptions",
            ["plan_code"],
            schema=SCHEMA,
        )

    if table_exists(bind, "marketplace_orders", schema=SCHEMA):
        if not column_exists(bind, "marketplace_orders", "price", schema=SCHEMA):
            op.add_column("marketplace_orders", sa.Column("price", sa.Numeric(18, 4), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "marketplace_orders", "discount", schema=SCHEMA):
            op.add_column("marketplace_orders", sa.Column("discount", sa.Numeric(18, 4), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "marketplace_orders", "final_price", schema=SCHEMA):
            op.add_column(
                "marketplace_orders", sa.Column("final_price", sa.Numeric(18, 4), nullable=True), schema=SCHEMA
            )
        if not column_exists(bind, "marketplace_orders", "commission", schema=SCHEMA):
            op.add_column(
                "marketplace_orders", sa.Column("commission", sa.Numeric(18, 4), nullable=True), schema=SCHEMA
            )
        if not column_exists(bind, "marketplace_orders", "completed_at", schema=SCHEMA):
            op.add_column(
                "marketplace_orders", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA
            )

    if table_exists(bind, "partner_plans", schema=SCHEMA):
        schema_prefix = _schema_prefix()
        existing = bind.execute(
            sa.text(
                f"SELECT 1 FROM {schema_prefix}partner_plans WHERE plan_code IN ('FREE', 'SELLER', 'PRO')"
            )
        ).fetchone()
        if not existing:
            op.bulk_insert(
                sa.table(
                    "partner_plans",
                    sa.Column("plan_code", sa.String),
                    sa.Column("title", sa.String),
                    sa.Column("description", sa.Text),
                    sa.Column("base_commission", sa.Numeric),
                    sa.Column("monthly_fee", sa.Numeric),
                    sa.Column("features", JSON_TYPE),
                    sa.Column("limits", JSON_TYPE),
                    schema=SCHEMA,
                ),
                [
                    {
                        "plan_code": "FREE",
                        "title": "FREE",
                        "description": "Базовый тариф без продвижения и аналитики.",
                        "base_commission": 0,
                        "monthly_fee": 0,
                        "features": {
                            "can_create_discounts": False,
                            "can_access_analytics": False,
                            "can_use_recommendations": False,
                            "priority_rank": 0,
                        },
                        "limits": {"products": 10},
                    },
                    {
                        "plan_code": "SELLER",
                        "title": "SELLER",
                        "description": "Тариф для активных продавцов с акциями и расширенными отчетами.",
                        "base_commission": 0,
                        "monthly_fee": 0,
                        "features": {
                            "can_create_discounts": True,
                            "can_access_analytics": True,
                            "can_use_recommendations": True,
                            "priority_rank": 1,
                        },
                        "limits": {"products": 100},
                    },
                    {
                        "plan_code": "PRO",
                        "title": "PRO SELLER",
                        "description": "Премиальный тариф без лимитов и с приоритетом в выдаче.",
                        "base_commission": 0,
                        "monthly_fee": 0,
                        "features": {
                            "can_create_discounts": True,
                            "can_access_analytics": True,
                            "can_use_recommendations": True,
                            "priority_rank": 2,
                        },
                        "limits": {"products": None},
                    },
                ],
            )


def downgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, "marketplace_orders", schema=SCHEMA):
        if column_exists(bind, "marketplace_orders", "completed_at", schema=SCHEMA):
            op.drop_column("marketplace_orders", "completed_at", schema=SCHEMA)
        if column_exists(bind, "marketplace_orders", "commission", schema=SCHEMA):
            op.drop_column("marketplace_orders", "commission", schema=SCHEMA)
        if column_exists(bind, "marketplace_orders", "final_price", schema=SCHEMA):
            op.drop_column("marketplace_orders", "final_price", schema=SCHEMA)
        if column_exists(bind, "marketplace_orders", "discount", schema=SCHEMA):
            op.drop_column("marketplace_orders", "discount", schema=SCHEMA)
        if column_exists(bind, "marketplace_orders", "price", schema=SCHEMA):
            op.drop_column("marketplace_orders", "price", schema=SCHEMA)

    if table_exists(bind, "partner_subscriptions", schema=SCHEMA):
        op.drop_table("partner_subscriptions", schema=SCHEMA)
    if table_exists(bind, "partner_plans", schema=SCHEMA):
        op.drop_table("partner_plans", schema=SCHEMA)

    if is_postgres(bind):
        bind.execute(sa.text(f"DROP TYPE IF EXISTS {_schema_prefix()}partner_subscription_status"))
        bind.execute(sa.text(f"DROP TYPE IF EXISTS {_schema_prefix()}partner_subscription_billing_cycle"))
