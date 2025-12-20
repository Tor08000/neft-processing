"""Add accounts and ledger tables

Revision ID: 20261201_0017_accounts_and_ledger
Revises: 20261125_0016_risk_rule_audit
Create Date: 2026-12-01 00:17:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import (
    column_exists,
    create_index_if_not_exists,
    drop_index_if_exists,
    pg_ensure_enum,
    safe_enum,
    table_exists,
)
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20261201_0017_accounts_and_ledger"
down_revision = "20261125_0016_risk_rule_audit"
branch_labels = None
depends_on = None

SCHEMA_RESOLUTION = resolve_db_schema()
SCHEMA = SCHEMA_RESOLUTION.schema
SCHEMA_PREFIX = f"{SCHEMA}." if SCHEMA else ""

ACCOUNT_TYPE_VALUES = ["CLIENT_MAIN", "CLIENT_CREDIT", "CARD_LIMIT", "TECHNICAL"]
ACCOUNT_OWNER_TYPE_VALUES = ["CLIENT", "PARTNER", "PLATFORM"]
ACCOUNT_STATUS_VALUES = ["ACTIVE", "FROZEN", "CLOSED"]
LEDGER_DIRECTION_VALUES = ["DEBIT", "CREDIT"]
POSTING_BATCH_TYPE_VALUES = ["AUTH", "HOLD", "COMMIT", "CAPTURE", "REFUND", "REVERSAL", "ADJUSTMENT"]
POSTING_BATCH_STATUS_VALUES = ["APPLIED", "REVERSED"]


def _account_type_enum(bind):
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(
            *ACCOUNT_TYPE_VALUES, name="accounttype", create_type=False
        )

    return sa.Enum(
        *ACCOUNT_TYPE_VALUES,
        name="accounttype",
        native_enum=False,
    )


def _account_status_enum(bind):
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(
            *ACCOUNT_STATUS_VALUES, name="accountstatus", create_type=False
        )

    return sa.Enum(
        *ACCOUNT_STATUS_VALUES,
        name="accountstatus",
        native_enum=False,
    )


def _ledger_direction_enum(bind):
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(
            *LEDGER_DIRECTION_VALUES, name="ledgerdirection", create_type=False
        )

    return sa.Enum(
        *LEDGER_DIRECTION_VALUES,
        name="ledgerdirection",
        native_enum=False,
    )


def _uuid_type(bind):
    if bind.dialect.name == "postgresql":
        return sa.dialects.postgresql.UUID(as_uuid=True)
    return sa.String(length=36)


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        pg_ensure_enum(bind, "accounttype", ACCOUNT_TYPE_VALUES, schema=SCHEMA)
        pg_ensure_enum(bind, "accountstatus", ACCOUNT_STATUS_VALUES, schema=SCHEMA)
        pg_ensure_enum(bind, "accountownertype", ACCOUNT_OWNER_TYPE_VALUES, schema=SCHEMA)
        pg_ensure_enum(bind, "ledgerdirection", LEDGER_DIRECTION_VALUES, schema=SCHEMA)
        pg_ensure_enum(bind, "postingbatchtype", POSTING_BATCH_TYPE_VALUES, schema=SCHEMA)
        pg_ensure_enum(bind, "postingbatchstatus", POSTING_BATCH_STATUS_VALUES, schema=SCHEMA)

    account_type_enum = _account_type_enum(bind)
    account_status_enum = _account_status_enum(bind)
    account_owner_enum = safe_enum(bind, "accountownertype", ACCOUNT_OWNER_TYPE_VALUES, schema=SCHEMA)
    ledger_direction_enum = _ledger_direction_enum(bind)
    json_variant = sa.JSON().with_variant(postgresql.JSONB, "postgresql")
    accounts_exists = table_exists(bind, "accounts", schema=SCHEMA)
    owner_type_exists = (
        column_exists(bind, "accounts", "owner_type", schema=SCHEMA) if accounts_exists else False
    )

    if not accounts_exists:
        op.create_table(
            "accounts",
            sa.Column(
                "id",
                sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                primary_key=True,
                autoincrement=True,
            ),
            sa.Column("client_id", sa.String(length=64), nullable=False, index=True),
            sa.Column("owner_type", account_owner_enum, nullable=False, server_default="CLIENT"),
            sa.Column("owner_id", sa.String(length=64), nullable=False, index=True),
            sa.Column("card_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.cards.id"), nullable=True),
            sa.Column("tariff_id", sa.String(length=64), nullable=True),
            sa.Column("currency", sa.String(length=8), nullable=False),
            sa.Column("type", account_type_enum, nullable=False),
            sa.Column("status", account_status_enum, nullable=False, server_default="ACTIVE"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
            schema=SCHEMA,
        )
        accounts_exists = True
        owner_type_exists = True
    elif not owner_type_exists:
        op.add_column(
            "accounts",
            sa.Column("owner_type", account_owner_enum, nullable=True, server_default="CLIENT"),
            schema=SCHEMA,
        )
        op.execute(f"UPDATE {SCHEMA_PREFIX}accounts SET owner_type = 'CLIENT' WHERE owner_type IS NULL")
        op.alter_column("accounts", "owner_type", nullable=False, server_default="CLIENT", schema=SCHEMA)
        owner_type_exists = True
    create_index_if_not_exists(bind, "ix_accounts_client_id", "accounts", ["client_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_accounts_card_id", "accounts", ["card_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_accounts_type", "accounts", ["type"], schema=SCHEMA)
    if owner_type_exists:
        create_index_if_not_exists(bind, "ix_accounts_owner_type", "accounts", ["owner_type"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_accounts_owner_id", "accounts", ["owner_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_accounts_status", "accounts", ["status"], schema=SCHEMA)

    if not table_exists(bind, "account_balances", schema=SCHEMA):
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
            sa.Column("hold_balance", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
            schema=SCHEMA,
        )

    if not table_exists(bind, "ledger_entries", schema=SCHEMA):
        op.create_table(
            "ledger_entries",
            sa.Column(
                "id",
                sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                primary_key=True,
                autoincrement=True,
            ),
            sa.Column("entry_id", _uuid_type(bind), nullable=False, unique=True),
            sa.Column("posting_id", _uuid_type(bind), nullable=False),
            sa.Column(
                "account_id",
                sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                sa.ForeignKey(f"{SCHEMA}.accounts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "operation_id",
                _uuid_type(bind),
                sa.ForeignKey(f"{SCHEMA}.operations.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("direction", ledger_direction_enum, nullable=False),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("currency", sa.String(length=8), nullable=False),
            sa.Column("balance_before", sa.Numeric(18, 4), nullable=True),
            sa.Column("balance_after", sa.Numeric(18, 4), nullable=True),
            sa.Column(
                "posted_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("value_date", sa.Date(), nullable=True),
            sa.Column("metadata", json_variant, nullable=True),
            schema=SCHEMA,
        )
    create_index_if_not_exists(bind, "ix_ledger_entries_account_id", "ledger_entries", ["account_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_ledger_entries_posting_id", "ledger_entries", ["posting_id"], schema=SCHEMA)
    create_index_if_not_exists(
        bind, "ix_ledger_entries_operation_id", "ledger_entries", ["operation_id"], schema=SCHEMA
    )
    create_index_if_not_exists(bind, "ix_ledger_entries_posted_at", "ledger_entries", ["posted_at"], schema=SCHEMA)
    create_index_if_not_exists(
        bind,
        "ix_ledger_entries_account_operation",
        "ledger_entries",
        ["account_id", "operation_id"],
        schema=SCHEMA,
    )

    if not table_exists(bind, "posting_batches", schema=SCHEMA):
        op.create_table(
            "posting_batches",
            sa.Column("id", _uuid_type(bind), primary_key=True, nullable=False),
            sa.Column("operation_id", _uuid_type(bind), nullable=True),
            sa.Column(
                "posting_type",
                sa.Enum(
                    "AUTH",
                    "HOLD",
                    "COMMIT",
                    "CAPTURE",
                    "REFUND",
                    "REVERSAL",
                    "ADJUSTMENT",
                    name="postingbatchtype",
                ),
                nullable=False,
            ),
            sa.Column(
                "status",
                sa.Enum("APPLIED", "REVERSED", name="postingbatchstatus"),
                nullable=False,
                server_default="APPLIED",
            ),
            sa.Column("idempotency_key", sa.String(length=255), nullable=False, unique=True),
            sa.Column("hash", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind, "ix_posting_batches_operation_id", "posting_batches", ["operation_id"], schema=SCHEMA
        )
        create_index_if_not_exists(
            bind, "ix_posting_batches_idempotency_key", "posting_batches", ["idempotency_key"], schema=SCHEMA
        )


def downgrade() -> None:
    bind = op.get_bind()

    drop_index_if_exists(
        bind, "ix_ledger_entries_posted_at", table_name="ledger_entries", schema=SCHEMA
    )
    drop_index_if_exists(
        bind, "ix_ledger_entries_operation_id", table_name="ledger_entries", schema=SCHEMA
    )
    drop_index_if_exists(
        bind, "ix_ledger_entries_account_id", table_name="ledger_entries", schema=SCHEMA
    )
    drop_index_if_exists(
        bind, "ix_ledger_entries_posting_id", table_name="ledger_entries", schema=SCHEMA
    )
    drop_index_if_exists(
        bind, "ix_ledger_entries_account_operation", table_name="ledger_entries", schema=SCHEMA
    )
    if table_exists(bind, "ledger_entries", schema=SCHEMA):
        op.drop_table("ledger_entries", schema=SCHEMA)

    drop_index_if_exists(
        bind, "ix_posting_batches_idempotency_key", table_name="posting_batches", schema=SCHEMA
    )
    drop_index_if_exists(bind, "ix_posting_batches_operation_id", table_name="posting_batches", schema=SCHEMA)
    if table_exists(bind, "posting_batches", schema=SCHEMA):
        op.drop_table("posting_batches", schema=SCHEMA)

    if table_exists(bind, "account_balances", schema=SCHEMA):
        op.drop_table("account_balances", schema=SCHEMA)

    drop_index_if_exists(bind, "ix_accounts_owner_id", table_name="accounts", schema=SCHEMA)
    drop_index_if_exists(bind, "ix_accounts_owner_type", table_name="accounts", schema=SCHEMA)
    drop_index_if_exists(bind, "ix_accounts_status", table_name="accounts", schema=SCHEMA)
    drop_index_if_exists(bind, "ix_accounts_type", table_name="accounts", schema=SCHEMA)
    drop_index_if_exists(bind, "ix_accounts_card_id", table_name="accounts", schema=SCHEMA)
    drop_index_if_exists(bind, "ix_accounts_client_id", table_name="accounts", schema=SCHEMA)
    if table_exists(bind, "accounts", schema=SCHEMA):
        op.drop_table("accounts", schema=SCHEMA)

    if bind.dialect.name == "postgresql":
        for enum_name in ("postingbatchstatus", "postingbatchtype", "ledgerdirection", "accountstatus", "accounttype", "accountownertype"):
            bind.exec_driver_sql(f'DROP TYPE IF EXISTS "{SCHEMA}".{enum_name}')
