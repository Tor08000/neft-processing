"""Internal ledger v1 tables.

Revision ID: 20291201_0056_internal_ledger_v1
Revises: 20291101_0055_legal_integrations_v2
Create Date: 2029-12-01 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20291201_0056_internal_ledger_v1"
down_revision = "20291101_0055_legal_integrations_v2"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

ACCOUNT_TYPES = [
    "CLIENT_AR",
    "CLIENT_CASH",
    "PLATFORM_REVENUE",
    "PLATFORM_FEES",
    "TAX_VAT",
    "PROVIDER_PAYABLE",
    "SUSPENSE",
]
ACCOUNT_STATUS = ["ACTIVE", "ARCHIVED"]
TRANSACTION_TYPES = [
    "INVOICE_ISSUED",
    "PAYMENT_APPLIED",
    "CREDIT_NOTE_APPLIED",
    "REFUND_APPLIED",
    "SETTLEMENT_ALLOCATION_CREATED",
    "ACCOUNTING_EXPORT_CONFIRMED",
]
ENTRY_DIRECTIONS = ["DEBIT", "CREDIT"]


def _uuid_type(bind):
    if getattr(bind.dialect, "name", None) == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(length=36)


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "internal_ledger_account_type", ACCOUNT_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "internal_ledger_account_status", ACCOUNT_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "internal_ledger_transaction_type", TRANSACTION_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "internal_ledger_entry_direction", ENTRY_DIRECTIONS, schema=SCHEMA)

    account_type_enum = safe_enum(bind, "internal_ledger_account_type", ACCOUNT_TYPES, schema=SCHEMA)
    account_status_enum = safe_enum(bind, "internal_ledger_account_status", ACCOUNT_STATUS, schema=SCHEMA)
    transaction_type_enum = safe_enum(bind, "internal_ledger_transaction_type", TRANSACTION_TYPES, schema=SCHEMA)
    entry_direction_enum = safe_enum(bind, "internal_ledger_entry_direction", ENTRY_DIRECTIONS, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "internal_ledger_accounts",
        sa.Column("id", _uuid_type(bind), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=True),
        sa.Column("account_type", account_type_enum, nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", account_status_enum, nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id",
            "client_id",
            "account_type",
            "currency",
            name="uq_internal_ledger_accounts_scope",
        ),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_internal_ledger_accounts_tenant",
        "internal_ledger_accounts",
        ["tenant_id"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "internal_ledger_transactions",
        sa.Column("id", _uuid_type(bind), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("transaction_type", transaction_type_enum, nullable=False),
        sa.Column("external_ref_type", sa.String(length=64), nullable=False),
        sa.Column("external_ref_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_internal_ledger_txn_idempotency"),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_internal_ledger_transactions_external_ref",
        "internal_ledger_transactions",
        ["external_ref_type", "external_ref_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_internal_ledger_transactions_idempotency",
        "internal_ledger_transactions",
        ["idempotency_key"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "internal_ledger_entries",
        sa.Column("id", _uuid_type(bind), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "ledger_transaction_id",
            _uuid_type(bind),
            sa.ForeignKey(f"{SCHEMA}.internal_ledger_transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            _uuid_type(bind),
            sa.ForeignKey(f"{SCHEMA}.internal_ledger_accounts.id"),
            nullable=False,
        ),
        sa.Column("direction", entry_direction_enum, nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("entry_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("meta", sa.JSON(), nullable=True),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_internal_ledger_entries_account_created",
        "internal_ledger_entries",
        ["account_id", "created_at"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_internal_ledger_entries_transaction",
        "internal_ledger_entries",
        ["ledger_transaction_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
