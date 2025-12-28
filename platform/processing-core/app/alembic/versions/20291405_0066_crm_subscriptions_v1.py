"""crm subscriptions v1 billing tables

Revision ID: 20291405_0066_crm_subscriptions_v1
Revises: 20291401_0065_crm_core_v1
Create Date: 2029-04-05 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import ensure_pg_enum, ensure_pg_enum_value, table_exists
from app.db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20291405_0066_crm_subscriptions_v1"
down_revision = "20291401_0065_crm_core_v1"
branch_labels = None
depends_on = None


CRM_BILLING_CYCLE = ["MONTHLY"]
CRM_SUBSCRIPTION_CHARGE_TYPE = ["BASE_FEE", "OVERAGE"]
CRM_USAGE_METRIC = [
    "CARDS_COUNT",
    "VEHICLES_COUNT",
    "DRIVERS_COUNT",
    "FUEL_TX_COUNT",
    "FUEL_VOLUME",
    "LOGISTICS_ORDERS",
]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "crm_billing_cycle", CRM_BILLING_CYCLE, schema=SCHEMA)
    ensure_pg_enum(bind, "crm_subscription_charge_type", CRM_SUBSCRIPTION_CHARGE_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "crm_usage_metric", CRM_USAGE_METRIC, schema=SCHEMA)
    ensure_pg_enum_value(bind, "crm_subscription_status", "PAUSED", schema=SCHEMA)
    ensure_pg_enum_value(bind, "document_type", "SUBSCRIPTION_INVOICE", schema=SCHEMA)
    ensure_pg_enum_value(bind, "document_type", "SUBSCRIPTION_ACT", schema=SCHEMA)
    ensure_pg_enum_value(bind, "legal_node_type", "SUBSCRIPTION", schema=SCHEMA)

    if table_exists(bind, "crm_tariff_plans", schema=SCHEMA):
        op.add_column("crm_tariff_plans", sa.Column("definition", sa.JSON, nullable=True), schema=SCHEMA)

    if table_exists(bind, "crm_subscriptions", schema=SCHEMA):
        op.add_column("crm_subscriptions", sa.Column("tariff_plan_id", sa.String(64), nullable=True), schema=SCHEMA)
        op.add_column(
            "crm_subscriptions",
            sa.Column(
                "billing_cycle",
                postgresql.ENUM(
                    *CRM_BILLING_CYCLE,
                    name="crm_billing_cycle",
                    schema=SCHEMA,
                    create_type=False,
                ),
                nullable=True,
            ),
            schema=SCHEMA,
        )
        op.add_column("crm_subscriptions", sa.Column("billing_day", sa.Integer, nullable=False, server_default="1"), schema=SCHEMA)
        op.add_column("crm_subscriptions", sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)
        op.add_column(
            "crm_subscriptions",
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            schema=SCHEMA,
        )
        op.add_column(
            "crm_subscriptions",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
            ),
            schema=SCHEMA,
        )
        op.execute(
            sa.text(
                f"UPDATE {SCHEMA}.crm_subscriptions SET tariff_plan_id = tariff_id WHERE tariff_plan_id IS NULL"
            )
        )
        op.execute(
            sa.text(
                f"UPDATE {SCHEMA}.crm_subscriptions SET billing_cycle = 'MONTHLY' WHERE billing_cycle IS NULL"
            )
        )
        op.alter_column("crm_subscriptions", "tariff_plan_id", nullable=False, schema=SCHEMA)
        op.alter_column("crm_subscriptions", "billing_cycle", nullable=False, schema=SCHEMA)

    if not table_exists(bind, "crm_subscription_charges", schema=SCHEMA):
        op.create_table(
            "crm_subscription_charges",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("subscription_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.crm_subscriptions.id"), nullable=False),
            sa.Column("billing_period_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.billing_periods.id"), nullable=False),
            sa.Column(
                "charge_type",
                postgresql.ENUM(
                    *CRM_SUBSCRIPTION_CHARGE_TYPE,
                    name="crm_subscription_charge_type",
                    schema=SCHEMA,
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("quantity", sa.Integer, nullable=False),
            sa.Column("unit_price", sa.BigInteger, nullable=False),
            sa.Column("amount", sa.BigInteger, nullable=False),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("source", sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_crm_subscription_charges_period",
            "crm_subscription_charges",
            ["subscription_id", "billing_period_id"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "crm_usage_counters", schema=SCHEMA):
        op.create_table(
            "crm_usage_counters",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("subscription_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.crm_subscriptions.id"), nullable=False),
            sa.Column("billing_period_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.billing_periods.id"), nullable=False),
            sa.Column(
                "metric",
                postgresql.ENUM(
                    *CRM_USAGE_METRIC,
                    name="crm_usage_metric",
                    schema=SCHEMA,
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("value", sa.BigInteger, nullable=False),
            sa.Column("limit_value", sa.BigInteger, nullable=True),
            sa.Column("overage", sa.BigInteger, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_crm_usage_counters_period",
            "crm_usage_counters",
            ["subscription_id", "billing_period_id"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    pass
