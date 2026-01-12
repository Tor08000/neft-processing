"""create money flow link type enum

Revision ID: 20297115_0116_create_money_flow_link_type_enum
Revises: 20297100_0115_merge_heads
Create Date: 2029-07-15 00:00:00.000000
"""

from __future__ import annotations

import re

from alembic import op
from sqlalchemy import text

from alembic_helpers import SCHEMA, is_postgres

revision = "20297115_0116_create_money_flow_link_type_enum"
down_revision = "20297100_0115_merge_heads"
branch_labels = None
depends_on = None

MONEY_FLOW_LINK_TYPES = [
    "GENERATES",
    "SETTLES",
    "POSTS",
    "FEEDS",
    "RELATES",
]


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", SCHEMA):
        raise RuntimeError(f"Unsafe schema name: {SCHEMA!r}")

    def sql_str(value: str) -> str:
        return value.replace("'", "''")

    values_params = {f"v{index}": value for index, value in enumerate(MONEY_FLOW_LINK_TYPES)}
    values_clause = ", ".join(f"(:v{index})" for index in range(len(MONEY_FLOW_LINK_TYPES)))
    values_sql = bind.execute(
        text(
            f"""
            SELECT string_agg(quote_literal(v), ', ')
            FROM (VALUES {values_clause}) AS t(v)
            """
        ),
        values_params,
    ).scalar()
    do_sql = f"""
    DO $$
    DECLARE
        schema_name text := '{sql_str(SCHEMA)}';
        values_sql text := '{sql_str(values_sql)}';
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = schema_name
              AND t.typname = 'money_flow_link_type'
        ) THEN
            EXECUTE 'CREATE TYPE {SCHEMA}.money_flow_link_type AS ENUM (' || values_sql || ')';
        END IF;
    END $$;
    """
    bind.exec_driver_sql(do_sql)


def downgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", SCHEMA):
        raise RuntimeError(f"Unsafe schema name: {SCHEMA!r}")
    bind.exec_driver_sql(f"DROP TYPE IF EXISTS {SCHEMA}.money_flow_link_type")
