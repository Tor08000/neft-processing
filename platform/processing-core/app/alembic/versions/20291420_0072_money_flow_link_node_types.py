"""money flow link node types

Revision ID: 20291420_0072_money_flow_link_node_types
Revises: 20291420_0071_subscriptions_v2_segments_and_rules
Create Date: 2029-04-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import bindparam, text
from sqlalchemy.types import Text

from app.alembic.utils import SCHEMA, ensure_pg_enum_value, is_postgres

revision = "20291420_0072_money_flow_link_node_types"
down_revision = "20291420_0071_subscriptions_v2_segments_and_rules"
branch_labels = None
depends_on = None

NEW_NODE_TYPES = [
    "SUBSCRIPTION_SEGMENT",
    "USAGE_COUNTER",
    "DOCUMENT",
]

BASE_NODE_TYPES = [
    # Source of truth: MoneyFlowLinkNodeType in app/models/money_flow_v3.py,
    # excluding NEW_NODE_TYPES introduced by this migration.
    "SUBSCRIPTION",
    "SUBSCRIPTION_CHARGE",
    "INVOICE",
    "PAYMENT",
    "REFUND",
    "FUEL_TX",
    "LOGISTICS_ORDER",
    "ACCOUNTING_EXPORT",
    "LEDGER_TX",
    "BILLING_PERIOD",
]


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return
    values_params = {f"v{index}": value for index, value in enumerate(BASE_NODE_TYPES)}
    values_clause = ", ".join(f"(:v{index})" for index in range(len(BASE_NODE_TYPES)))
    values_sql = bind.execute(
        text(
            f"""
            SELECT string_agg(quote_literal(v), ', ')
            FROM (VALUES {values_clause}) AS t(v)
            """
        ),
        values_params,
    ).scalar()
    sql = text(
        """
        DO $$
        DECLARE
            schema_name text := (:schema)::text;
            enum_name text := (:enum_name)::text;
            values_sql text := (:values_sql)::text;
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE n.nspname = schema_name
                  AND t.typname = enum_name
            ) THEN
                EXECUTE format(
                    'CREATE TYPE %I.%I AS ENUM (%s)',
                    schema_name,
                    enum_name,
                    values_sql
                );
            END IF;
        END $$;
        """
    ).bindparams(
        bindparam("schema", type_=Text()),
        bindparam("enum_name", type_=Text()),
        bindparam("values_sql", type_=Text()),
    )
    bind.execute(
        sql,
        {
            "schema": SCHEMA,
            "enum_name": "money_flow_link_node_type",
            "values_sql": values_sql,
        },
    )
    for value in NEW_NODE_TYPES:
        ensure_pg_enum_value(bind, "money_flow_link_node_type", value, schema=SCHEMA)


def downgrade() -> None:
    pass
