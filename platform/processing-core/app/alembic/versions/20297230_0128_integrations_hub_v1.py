"""Integrations hub v1 tables.

Revision ID: 20297230_0128_integrations_hub_v1
Revises: 20297220_0127_subscription_event_price_version_capture
Create Date: 2029-09-12 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import (
    SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)


revision = "20297230_0128_integrations_hub_v1"
down_revision = "20297220_0127_subscription_event_price_version_capture"
branch_labels = None
depends_on = None


INTEGRATION_TYPES = ["ONEC", "BANK"]
INTEGRATION_EXPORT_STATUSES = ["CREATED", "EXPORTED", "FAILED"]
BANK_STATEMENT_STATUSES = ["IMPORTED", "PARSED", "FAILED"]
BANK_TRANSACTION_DIRECTIONS = ["IN", "OUT"]
BANK_RECON_STATUS = ["STARTED", "COMPLETED", "FAILED"]
BANK_RECON_MATCH_TYPES = ["EXACT_REF", "INN_AMOUNT_DATE", "FUZZY"]
BANK_RECON_DIFF_SOURCES = ["LEDGER", "BANK"]
BANK_RECON_DIFF_REASONS = [
    "NOT_FOUND",
    "AMOUNT_MISMATCH",
    "DATE_MISMATCH",
    "DUPLICATE_MATCH",
    "COUNTERPARTY_MISMATCH",
]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "integration_type", INTEGRATION_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "integration_export_status", INTEGRATION_EXPORT_STATUSES, schema=SCHEMA)
    ensure_pg_enum(bind, "bank_statement_status", BANK_STATEMENT_STATUSES, schema=SCHEMA)
    ensure_pg_enum(bind, "bank_transaction_direction", BANK_TRANSACTION_DIRECTIONS, schema=SCHEMA)
    ensure_pg_enum(bind, "bank_reconciliation_status", BANK_RECON_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "bank_reconciliation_match_type", BANK_RECON_MATCH_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "bank_reconciliation_diff_source", BANK_RECON_DIFF_SOURCES, schema=SCHEMA)
    ensure_pg_enum(bind, "bank_reconciliation_diff_reason", BANK_RECON_DIFF_REASONS, schema=SCHEMA)

    integration_type_enum = safe_enum(bind, "integration_type", INTEGRATION_TYPES, schema=SCHEMA)
    export_status_enum = safe_enum(bind, "integration_export_status", INTEGRATION_EXPORT_STATUSES, schema=SCHEMA)
    statement_status_enum = safe_enum(bind, "bank_statement_status", BANK_STATEMENT_STATUSES, schema=SCHEMA)
    direction_enum = safe_enum(bind, "bank_transaction_direction", BANK_TRANSACTION_DIRECTIONS, schema=SCHEMA)
    recon_status_enum = safe_enum(bind, "bank_reconciliation_status", BANK_RECON_STATUS, schema=SCHEMA)
    recon_match_enum = safe_enum(bind, "bank_reconciliation_match_type", BANK_RECON_MATCH_TYPES, schema=SCHEMA)
    recon_source_enum = safe_enum(bind, "bank_reconciliation_diff_source", BANK_RECON_DIFF_SOURCES, schema=SCHEMA)
    recon_reason_enum = safe_enum(bind, "bank_reconciliation_diff_reason", BANK_RECON_DIFF_REASONS, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "integration_mappings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("integration_type", integration_type_enum, nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("source_field", sa.String(length=128), nullable=False),
        sa.Column("target_field", sa.String(length=128), nullable=False),
        sa.Column("transform", sa.String(length=128), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "integration_files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "integration_exports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("integration_type", integration_type_enum, nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", export_status_enum, nullable=False),
        sa.Column("file_id", sa.String(length=36), sa.ForeignKey("integration_files.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "bank_statements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("bank_code", sa.String(length=32), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by", sa.String(length=64), nullable=True),
        sa.Column("file_id", sa.String(length=36), sa.ForeignKey("integration_files.id"), nullable=True),
        sa.Column("status", statement_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "bank_transactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("statement_id", sa.String(length=36), sa.ForeignKey("bank_statements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("direction", direction_enum, nullable=False),
        sa.Column("counterparty", sa.String(length=255), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("external_ref", sa.String(length=128), nullable=True),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "bank_reconciliation_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("statement_id", sa.String(length=36), sa.ForeignKey("bank_statements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", recon_status_enum, nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "bank_reconciliation_matches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("bank_reconciliation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bank_tx_id", sa.String(length=36), sa.ForeignKey("bank_transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", sa.String(length=36), nullable=True),
        sa.Column("match_type", recon_match_enum, nullable=False),
        sa.Column("score", sa.Numeric(5, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "bank_reconciliation_diffs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("bank_reconciliation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", recon_source_enum, nullable=False),
        sa.Column("tx_id", sa.String(length=64), nullable=False),
        sa.Column("reason", recon_reason_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_integration_mappings_type_entity",
        "integration_mappings",
        ["integration_type", "entity_type"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_integration_exports_type_status",
        "integration_exports",
        ["integration_type", "status"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_bank_statements_bank_period",
        "bank_statements",
        ["bank_code", "period_end"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_bank_transactions_statement",
        "bank_transactions",
        ["statement_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_bank_transactions_hash",
        "bank_transactions",
        ["hash"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_bank_reconciliation_runs_statement",
        "bank_reconciliation_runs",
        ["statement_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_bank_reconciliation_matches_run",
        "bank_reconciliation_matches",
        ["run_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_bank_reconciliation_diffs_run",
        "bank_reconciliation_diffs",
        ["run_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_integration_files_created",
        "integration_files",
        ["created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    pass
