# services/core-api/app/alembic/versions/2025_11_01_init.py
from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import create_table_if_not_exists, ensure_pg_enum, safe_enum

revision = "2025_11_01_init"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DB_SCHEMA", "public")

ACCOUNT_TYPE_VALUES = ["CLIENT_MAIN", "CLIENT_CREDIT", "CARD_LIMIT", "TECHNICAL"]
ACCOUNT_STATUS_VALUES = ["ACTIVE", "FROZEN", "CLOSED"]
LEDGER_DIRECTION_VALUES = ["DEBIT", "CREDIT"]

LIMIT_CONFIG_SCOPE_VALUES = ["GLOBAL", "CLIENT", "CARD", "TARIFF"]
LIMIT_WINDOW_VALUES = ["PER_TX", "DAILY", "MONTHLY"]
LIMIT_TYPE_VALUES = ["DAILY_VOLUME", "DAILY_AMOUNT", "MONTHLY_AMOUNT", "CREDIT_LIMIT"]


def _json_type(bind):
    return postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()


def _uuid_type(bind):
    return postgresql.UUID(as_uuid=True) if bind.dialect.name == "postgresql" else sa.String(36)


def _create_schema(bind) -> None:
    if getattr(getattr(bind, "dialect", None), "name", None) != "postgresql":
        return

    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))


def _assert_fk_column_types(bind) -> None:
    if getattr(getattr(bind, "dialect", None), "name", None) != "postgresql":
        return

    results = bind.execute(
        sa.text(
            """
            select table_name, column_name, data_type, udt_name
            from information_schema.columns
            where table_schema = :schema
              and (table_name, column_name) in (
                (:operations, 'client_id'),
                (:operations, 'card_id'),
                (:operations, 'merchant_id'),
                (:operations, 'terminal_id'),
                ('clients', 'id'),
                ('cards', 'id'),
                ('merchants', 'id'),
                ('terminals', 'id')
              )
            order by table_name, column_name
            """
        ),
        {"schema": SCHEMA, "operations": "operations"},
    ).mappings()

    types = {
        (row["table_name"], row["column_name"]): (row["data_type"], row["udt_name"])
        for row in results
    }

    pairs = [
        (("operations", "client_id"), ("clients", "id")),
        (("operations", "card_id"), ("cards", "id")),
        (("operations", "merchant_id"), ("merchants", "id")),
        (("operations", "terminal_id"), ("terminals", "id")),
    ]

    missing = [pair for pair in pairs if pair[0] not in types or pair[1] not in types]
    assert not missing, f"Missing columns for FK type assertion: {missing}"

    mismatches = {
        (lhs, rhs): (types.get(lhs), types.get(rhs))
        for lhs, rhs in pairs
        if types.get(lhs) != types.get(rhs)
    }
    assert not mismatches, f"FK column types mismatch: {mismatches}"


def upgrade():
    bind = op.get_bind()
    _create_schema(bind)

    ensure_pg_enum(bind, "accounttype", ACCOUNT_TYPE_VALUES, schema=SCHEMA)
    ensure_pg_enum(bind, "accountstatus", ACCOUNT_STATUS_VALUES, schema=SCHEMA)
    ensure_pg_enum(bind, "ledgerdirection", LEDGER_DIRECTION_VALUES, schema=SCHEMA)
    ensure_pg_enum(bind, "limitconfigscope", LIMIT_CONFIG_SCOPE_VALUES, schema=SCHEMA)
    ensure_pg_enum(bind, "limittype", LIMIT_TYPE_VALUES, schema=SCHEMA)
    ensure_pg_enum(bind, "limitwindow", LIMIT_WINDOW_VALUES, schema=SCHEMA)

    account_type_enum = safe_enum(bind, "accounttype", ACCOUNT_TYPE_VALUES, schema=SCHEMA)
    account_status_enum = safe_enum(bind, "accountstatus", ACCOUNT_STATUS_VALUES, schema=SCHEMA)
    ledger_direction_enum = safe_enum(bind, "ledgerdirection", LEDGER_DIRECTION_VALUES, schema=SCHEMA)
    limit_config_scope_enum = safe_enum(bind, "limitconfigscope", LIMIT_CONFIG_SCOPE_VALUES, schema=SCHEMA)
    limit_type_enum = safe_enum(bind, "limittype", LIMIT_TYPE_VALUES, schema=SCHEMA)
    limit_window_enum = safe_enum(bind, "limitwindow", LIMIT_WINDOW_VALUES, schema=SCHEMA)

    json_type = _json_type(bind)
    uuid_type = _uuid_type(bind)

    create_table_if_not_exists(
        bind,
        "tariff_plans",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("params", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "clients",
        sa.Column(
            "id",
            uuid_type,
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()") if bind.dialect.name == "postgresql" else None,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "cards",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("pan_masked", sa.String(length=32), nullable=True),
        sa.Column("expires_at", sa.String(length=16), nullable=True),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "merchants",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "terminals",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("merchant_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.merchants.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "operations",
        sa.Column("operation_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()") if bind.dialect.name == "postgresql" else None,
            nullable=False,
        ),
        sa.Column("operation_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("merchant_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.merchants.id"), nullable=False),
        sa.Column("terminal_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.terminals.id"), nullable=False),
        sa.Column("client_id", uuid_type, sa.ForeignKey(f"{SCHEMA}.clients.id"), nullable=False),
        sa.Column("card_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.cards.id"), nullable=False),
        sa.Column("accounts", json_type, nullable=True),
        sa.Column("posting_result", json_type, nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("authorized", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("response_code", sa.String(length=16), nullable=False),
        sa.Column("response_message", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("daily_limit", sa.BigInteger(), nullable=True),
        sa.Column("limit_per_tx", sa.BigInteger(), nullable=True),
        sa.Column("used_today", sa.BigInteger(), nullable=True),
        sa.Column("new_used_today", sa.BigInteger(), nullable=True),
        sa.Column("parent_operation_id", sa.String(length=64), nullable=True),
        sa.Column("mcc", sa.String(length=32), nullable=True),
        sa.Column("product_code", sa.String(length=64), nullable=True),
        sa.Column("product_category", sa.String(length=64), nullable=True),
        sa.Column("tx_type", sa.String(length=32), nullable=True),
        sa.Column("captured_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("refunded_amount", sa.BigInteger(), nullable=False, server_default="0"),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "accounts",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.clients.id"), nullable=False),
        sa.Column("card_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.cards.id"), nullable=True),
        sa.Column("tariff_id", sa.String(length=64), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("type", account_type_enum, nullable=False),
        sa.Column("status", account_status_enum, nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "account_balances",
        sa.Column(
            "account_id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey(f"{SCHEMA}.accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("current_balance", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("available_balance", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "ledger_entries",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey(f"{SCHEMA}.accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "operation_id",
            sa.String(length=64),
            sa.ForeignKey(f"{SCHEMA}.operations.operation_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("direction", ledger_direction_enum, nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("balance_after", sa.Numeric(18, 4), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("value_date", sa.Date(), nullable=True),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "limit_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scope", limit_config_scope_enum, nullable=False),
        sa.Column("subject_ref", sa.String(length=64), nullable=False),
        sa.Column("limit_type", limit_type_enum, nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.Column(
            "window",
            limit_window_enum,
            nullable=False,
            server_default=sa.text("'DAILY'::limitwindow") if bind.dialect.name == "postgresql" else sa.text("'DAILY'"),
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("tariff_plan_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.tariff_plans.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )

    _assert_fk_column_types(bind)


def downgrade():
    for table in (
        "limit_configs",
        "ledger_entries",
        "account_balances",
        "accounts",
        "operations",
        "terminals",
        "merchants",
        "cards",
        "clients",
        "tariff_plans",
    ):
        op.drop_table(table, schema=SCHEMA)
