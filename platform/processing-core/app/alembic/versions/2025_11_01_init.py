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

def downgrade():
    for table in (
        "terminals",
        "merchants",
        "cards",
        "clients",
        "tariff_plans",
    ):
        op.drop_table(table, schema=SCHEMA)
