"""Authoritative bootstrap for core tables.

This revision must create the first batch of core tables so an upgrade on an
empty database cannot silently reach ``head`` without emitting any DDL. Earlier
versions of the repository kept this migration empty and relied on external SQL
bootstrap, which produced a "no-op" Alembic pipeline. The upgrade now creates
the base tables explicitly via ``op.create_table``.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.helpers import DB_SCHEMA, ensure_pg_enum, safe_enum
from app.db import resolve_db_schema, schema_resolution_line

# revision identifiers, used by Alembic.
revision = "20251112_0001_core"
down_revision = "2025_11_01_init"
branch_labels = None
depends_on = None


SCHEMA, SCHEMA_SOURCE = resolve_db_schema()

ACCOUNT_TYPE_VALUES = ["CLIENT_MAIN", "CLIENT_CREDIT", "CARD_LIMIT", "TECHNICAL"]
ACCOUNT_STATUS_VALUES = ["ACTIVE", "FROZEN", "CLOSED"]
LEDGER_DIRECTION_VALUES = ["DEBIT", "CREDIT"]

LIMIT_CONFIG_SCOPE_VALUES = ["GLOBAL", "CLIENT", "CARD", "TARIFF"]
LIMIT_WINDOW_VALUES = ["PER_TX", "DAILY", "MONTHLY"]
LIMIT_TYPE_VALUES = ["DAILY_VOLUME", "DAILY_AMOUNT", "MONTHLY_AMOUNT", "CREDIT_LIMIT"]


def _json_type(bind: sa.engine.Connection):
    return postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()


def _uuid_type(bind: sa.engine.Connection):
    return postgresql.UUID(as_uuid=True) if bind.dialect.name == "postgresql" else sa.String(36)


def _ensure_schema(bind: sa.engine.Connection) -> None:
    if getattr(getattr(bind, "dialect", None), "name", None) != "postgresql":
        return

    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_schema(bind)

    print(f"[20251112_0001_core] {schema_resolution_line(SCHEMA, SCHEMA_SOURCE)}")

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

    op.create_table(
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
        sa.Column("merchant_id", sa.String(length=64), nullable=False),
        sa.Column("terminal_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", uuid_type, nullable=False),
        sa.Column("card_id", sa.String(length=64), nullable=False),
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

    op.create_table(
        "accounts",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("client_id", uuid_type, nullable=False),
        sa.Column("card_id", sa.String(length=64), nullable=True),
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

    op.create_table(
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

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), nullable=False),
        sa.Column("operation_id", sa.String(length=64), nullable=True),
        sa.Column("direction", ledger_direction_enum, nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("balance_after", sa.Numeric(18, 4), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], [f"{SCHEMA}.accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["operation_id"], [f"{SCHEMA}.operations.operation_id"], ondelete="SET NULL"
        ),
        schema=SCHEMA,
    )

    op.create_table(
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
        sa.Column("tariff_plan_id", sa.String(length=64), nullable=True),
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

def downgrade() -> None:
    for table in (
        "limit_configs",
        "ledger_entries",
        "account_balances",
        "accounts",
        "operations",
    ):
        op.drop_table(table, schema=SCHEMA)
