"""Add client reconciliation, document acknowledgements, and invoice threads.

Revision ID: 20280315_0042_client_actions_v1
Revises: 20280301_0041_payout_exports_bank_format
Create Date: 2028-03-15 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_index_if_exists,
    drop_pg_enum_if_exists,
    drop_table_if_exists,
    ensure_pg_enum,
    safe_enum,
)
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20280315_0042_client_actions_v1"
down_revision = "20280301_0041_payout_exports_bank_format"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

RECONCILIATION_REQUEST_STATUS = [
    "NEW",
    "IN_PROGRESS",
    "READY",
    "SENT",
    "REJECTED",
    "CANCELLED",
]
INVOICE_THREAD_STATUS = ["OPEN", "CLOSED"]
INVOICE_MESSAGE_SENDER = ["CLIENT", "SUPPORT"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "reconciliation_request_status", RECONCILIATION_REQUEST_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "invoice_thread_status", INVOICE_THREAD_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "invoice_message_sender_type", INVOICE_MESSAGE_SENDER, schema=SCHEMA)

    reconciliation_status_enum = safe_enum(
        bind,
        "reconciliation_request_status",
        RECONCILIATION_REQUEST_STATUS,
        schema=SCHEMA,
    )
    invoice_thread_status_enum = safe_enum(bind, "invoice_thread_status", INVOICE_THREAD_STATUS, schema=SCHEMA)
    invoice_message_sender_enum = safe_enum(
        bind,
        "invoice_message_sender_type",
        INVOICE_MESSAGE_SENDER,
        schema=SCHEMA,
    )

    invoices_fk = "invoices.id" if not SCHEMA else f"{SCHEMA}.invoices.id"
    threads_fk = "invoice_threads.id" if not SCHEMA else f"{SCHEMA}.invoice_threads.id"

    create_table_if_not_exists(
        bind,
        "reconciliation_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("status", reconciliation_status_enum, nullable=False, server_default=RECONCILIATION_REQUEST_STATUS[0]),
        sa.Column("requested_by_user_id", sa.Text(), nullable=True),
        sa.Column("requested_by_email", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("result_object_key", sa.Text(), nullable=True),
        sa.Column("result_bucket", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("date_from <= date_to", name="ck_reconciliation_requests_period"),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "document_acknowledgements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("ack_by_user_id", sa.Text(), nullable=True),
        sa.Column("ack_by_email", sa.Text(), nullable=True),
        sa.Column("ack_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.UniqueConstraint("client_id", "document_type", "document_id", name="uq_document_acknowledgements_scope"),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "invoice_threads",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("invoice_id", sa.String(length=36), sa.ForeignKey(invoices_fk), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("status", invoice_thread_status_enum, nullable=False, server_default=INVOICE_THREAD_STATUS[0]),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("invoice_id", name="uq_invoice_thread_invoice"),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "invoice_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("thread_id", sa.String(length=36), sa.ForeignKey(threads_fk), nullable=False),
        sa.Column("sender_type", invoice_message_sender_enum, nullable=False),
        sa.Column("sender_user_id", sa.Text(), nullable=True),
        sa.Column("sender_email", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_reconciliation_requests_client_period",
        "reconciliation_requests",
        ["client_id", "date_from", "date_to"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_reconciliation_requests_status",
        "reconciliation_requests",
        ["status"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_document_acknowledgements_client_doc",
        "document_acknowledgements",
        ["client_id", "document_type", "document_id"],
        unique=True,
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_invoice_threads_invoice",
        "invoice_threads",
        ["invoice_id"],
        unique=True,
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_invoice_threads_client",
        "invoice_threads",
        ["client_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_invoice_messages_thread",
        "invoice_messages",
        ["thread_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_invoice_messages_sender",
        "invoice_messages",
        ["sender_type"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()

    drop_index_if_exists(bind, "ix_invoice_messages_sender", schema=SCHEMA)
    drop_index_if_exists(bind, "ix_invoice_messages_thread", schema=SCHEMA)
    drop_index_if_exists(bind, "ix_invoice_threads_client", schema=SCHEMA)
    drop_index_if_exists(bind, "ix_invoice_threads_invoice", schema=SCHEMA)
    drop_index_if_exists(bind, "ix_document_acknowledgements_client_doc", schema=SCHEMA)
    drop_index_if_exists(bind, "ix_reconciliation_requests_status", schema=SCHEMA)
    drop_index_if_exists(bind, "ix_reconciliation_requests_client_period", schema=SCHEMA)

    drop_table_if_exists(bind, "invoice_messages", schema=SCHEMA)
    drop_table_if_exists(bind, "invoice_threads", schema=SCHEMA)
    drop_table_if_exists(bind, "document_acknowledgements", schema=SCHEMA)
    drop_table_if_exists(bind, "reconciliation_requests", schema=SCHEMA)

    drop_pg_enum_if_exists(bind, "invoice_message_sender_type", schema=SCHEMA)
    drop_pg_enum_if_exists(bind, "invoice_thread_status", schema=SCHEMA)
    drop_pg_enum_if_exists(bind, "reconciliation_request_status", schema=SCHEMA)
