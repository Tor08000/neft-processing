"""Add bank statement imports and transactions.

Revision ID: 20299210_0149_bank_statement_imports
Revises: 20299180_0148_org_subscription_suspend_blocked_until
Create Date: 2026-03-01 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import (
    DB_SCHEMA,
    SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)
from sqlalchemy.dialects import postgresql


revision = "20299210_0149_bank_statement_imports"
down_revision = "20299180_0148_org_subscription_suspend_blocked_until"
branch_labels = None
depends_on = None


BANK_STATEMENT_IMPORT_STATUS = ["IMPORTED", "PARSED", "FAILED"]
BANK_STATEMENT_MATCH_STATUS = ["UNMATCHED", "MATCHED", "AMBIGUOUS", "IGNORED"]


def _schema_prefix() -> str:
    if not SCHEMA:
        return ""
    return f"{SCHEMA}."


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "bank_statement_import_status", BANK_STATEMENT_IMPORT_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "bank_statement_match_status", BANK_STATEMENT_MATCH_STATUS, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "bank_statement_imports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("uploaded_by_admin", sa.String(length=128), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("file_object_key", sa.Text(), nullable=False),
        sa.Column("format", sa.String(length=32), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=True),
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "bank_statement_import_status",
                BANK_STATEMENT_IMPORT_STATUS,
                schema=SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_bank_statement_imports_created",
        "bank_statement_imports",
        ["uploaded_at"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "bank_statement_transactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("import_id", sa.String(length=36), nullable=False),
        sa.Column("bank_tx_id", sa.String(length=128), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("payer_name", sa.String(length=255), nullable=True),
        sa.Column("payer_inn", sa.String(length=32), nullable=True),
        sa.Column("reference", sa.String(length=128), nullable=True),
        sa.Column("purpose_text", sa.Text(), nullable=True),
        sa.Column("raw_json", _json_type(), nullable=True),
        sa.Column(
            "matched_status",
            safe_enum(bind, "bank_statement_match_status", BANK_STATEMENT_MATCH_STATUS, schema=SCHEMA),
            nullable=False,
        ),
        sa.Column("matched_invoice_id", sa.String(length=36), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["import_id"], [f"{_schema_prefix()}bank_statement_imports.id"], ondelete="CASCADE"),
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_bank_statement_transactions_tx_id",
        "bank_statement_transactions",
        ["bank_tx_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_bank_statement_transactions_import",
        "bank_statement_transactions",
        ["import_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_bank_statement_transactions_status",
        "bank_statement_transactions",
        ["matched_status"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind is None:
        return
    op.drop_table("bank_statement_transactions", schema=DB_SCHEMA)
    op.drop_table("bank_statement_imports", schema=DB_SCHEMA)
