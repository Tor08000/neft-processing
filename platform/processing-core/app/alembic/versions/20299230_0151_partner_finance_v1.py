"""Partner settlements finance tables

Revision ID: 20299230_0151_partner_finance_v1
Revises: 20299220_0150_partner_core_tables
Create Date: 2024-09-23 00:00:00
"""

from alembic import op
import sqlalchemy as sa

from alembic_helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_table_if_exists,
    ensure_pg_enum,
    safe_enum,
)
from db.schema import resolve_db_schema


# revision identifiers, used by Alembic.
revision = "20299230_0151_partner_finance_v1"
down_revision = "20299220_0150_partner_core_tables"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

LEDGER_TYPES = [
    "EARNED",
    "SLA_PENALTY",
    "ADJUSTMENT",
    "PAYOUT_REQUESTED",
    "PAYOUT_APPROVED",
    "PAYOUT_PAID",
]
LEDGER_DIRECTIONS = ["DEBIT", "CREDIT"]
PAYOUT_STATUSES = ["REQUESTED", "APPROVED", "REJECTED", "PAID"]
DOCUMENT_STATUSES = ["DRAFT", "ISSUED", "PAID"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "partner_ledger_entry_type", LEDGER_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "partner_ledger_direction", LEDGER_DIRECTIONS, schema=SCHEMA)
    ensure_pg_enum(bind, "partner_payout_request_status", PAYOUT_STATUSES, schema=SCHEMA)
    ensure_pg_enum(bind, "partner_document_status", DOCUMENT_STATUSES, schema=SCHEMA)

    ledger_type_enum = safe_enum(bind, "partner_ledger_entry_type", LEDGER_TYPES, schema=SCHEMA)
    ledger_direction_enum = safe_enum(bind, "partner_ledger_direction", LEDGER_DIRECTIONS, schema=SCHEMA)
    payout_status_enum = safe_enum(bind, "partner_payout_request_status", PAYOUT_STATUSES, schema=SCHEMA)
    document_status_enum = safe_enum(bind, "partner_document_status", DOCUMENT_STATUSES, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "partner_accounts",
        sa.Column("org_id", sa.String(length=36), primary_key=True),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="RUB"),
        sa.Column("balance_available", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("balance_pending", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("balance_blocked", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_ledger_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("partner_org_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("order_id", sa.String(length=36), nullable=True, index=True),
        sa.Column("entry_type", ledger_type_enum, nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("direction", ledger_direction_enum, nullable=False),
        sa.Column("meta_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_payout_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("partner_org_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("status", payout_status_enum, nullable=False, server_default=PAYOUT_STATUSES[0]),
        sa.Column("requested_by", sa.String(length=36), nullable=True),
        sa.Column("approved_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_invoices",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("partner_org_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("period_from", sa.Date, nullable=False),
        sa.Column("period_to", sa.Date, nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("status", document_status_enum, nullable=False, server_default=DOCUMENT_STATUSES[0]),
        sa.Column("pdf_object_key", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_acts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("partner_org_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("period_from", sa.Date, nullable=False),
        sa.Column("period_to", sa.Date, nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("status", document_status_enum, nullable=False, server_default=DOCUMENT_STATUSES[0]),
        sa.Column("pdf_object_key", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_partner_ledger_partner_created",
        "partner_ledger_entries",
        ["partner_org_id", "created_at"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_partner_ledger_order",
        "partner_ledger_entries",
        ["order_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_partner_payout_requests_partner_status",
        "partner_payout_requests",
        ["partner_org_id", "status"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_partner_invoices_partner_period",
        "partner_invoices",
        ["partner_org_id", "period_from", "period_to"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_partner_acts_partner_period",
        "partner_acts",
        ["partner_org_id", "period_from", "period_to"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()
    drop_table_if_exists(bind, "partner_acts", schema=SCHEMA)
    drop_table_if_exists(bind, "partner_invoices", schema=SCHEMA)
    drop_table_if_exists(bind, "partner_payout_requests", schema=SCHEMA)
    drop_table_if_exists(bind, "partner_ledger_entries", schema=SCHEMA)
    drop_table_if_exists(bind, "partner_accounts", schema=SCHEMA)

    # enums are left in place for safety across deployments
