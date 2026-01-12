"""Add documents registry tables.

Revision ID: 0044_documents_registry
Revises: 0043_client_actions_enterprise
Create Date: 2028-03-25 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from alembic_helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)
from db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "0044_documents_registry"
down_revision = "0043_client_actions_enterprise"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

DOCUMENT_TYPES = ["INVOICE", "ACT", "RECONCILIATION_ACT", "CLOSING_PACKAGE"]
DOCUMENT_STATUSES = ["DRAFT", "GENERATED", "SENT", "ACKNOWLEDGED", "CANCELLED"]
DOCUMENT_FILE_TYPES = ["PDF", "XLSX"]
CLOSING_PACKAGE_STATUSES = ["DRAFT", "GENERATED", "SENT", "ACKNOWLEDGED", "CANCELLED"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "document_type", DOCUMENT_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "document_status", DOCUMENT_STATUSES, schema=SCHEMA)
    ensure_pg_enum(bind, "document_file_type", DOCUMENT_FILE_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "closing_package_status", CLOSING_PACKAGE_STATUSES, schema=SCHEMA)

    document_type_enum = safe_enum(bind, "document_type", DOCUMENT_TYPES, schema=SCHEMA)
    document_status_enum = safe_enum(bind, "document_status", DOCUMENT_STATUSES, schema=SCHEMA)
    document_file_type_enum = safe_enum(bind, "document_file_type", DOCUMENT_FILE_TYPES, schema=SCHEMA)
    closing_package_status_enum = safe_enum(bind, "closing_package_status", CLOSING_PACKAGE_STATUSES, schema=SCHEMA)

    documents_fk = "documents.id" if not SCHEMA else f"{SCHEMA}.documents.id"

    create_table_if_not_exists(
        bind,
        "documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("document_type", document_type_enum, nullable=False),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=False),
        sa.Column("status", document_status_enum, nullable=False, server_default=DOCUMENT_STATUSES[0]),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("number", sa.Text(), nullable=True),
        sa.Column("source_entity_type", sa.Text(), nullable=True),
        sa.Column("source_entity_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ack_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_actor_type", sa.String(length=32), nullable=True),
        sa.Column("created_by_actor_id", sa.Text(), nullable=True),
        sa.Column("created_by_email", sa.Text(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.CheckConstraint("period_from <= period_to", name="ck_documents_period"),
        sa.UniqueConstraint(
            "tenant_id",
            "client_id",
            "document_type",
            "period_from",
            "period_to",
            "version",
            name="uq_documents_scope",
        ),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "document_files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey(documents_fk), nullable=False),
        sa.Column("file_type", document_file_type_enum, nullable=False),
        sa.Column("bucket", sa.Text(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.UniqueConstraint("document_id", "file_type", name="uq_document_files_type"),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "closing_packages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=False),
        sa.Column("status", closing_package_status_enum, nullable=False, server_default=CLOSING_PACKAGE_STATUSES[0]),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("invoice_document_id", sa.String(length=36), sa.ForeignKey(documents_fk), nullable=True),
        sa.Column("act_document_id", sa.String(length=36), sa.ForeignKey(documents_fk), nullable=True),
        sa.Column("recon_document_id", sa.String(length=36), sa.ForeignKey(documents_fk), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ack_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.CheckConstraint("period_from <= period_to", name="ck_closing_packages_period"),
        sa.UniqueConstraint(
            "tenant_id",
            "client_id",
            "period_from",
            "period_to",
            "version",
            name="uq_closing_packages_scope",
        ),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_documents_client_type_period",
        "documents",
        ["client_id", "document_type", "period_from", "period_to"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_documents_status", "documents", ["status"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_document_files_document", "document_files", ["document_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_closing_packages_client", "closing_packages", ["client_id"], schema=SCHEMA)


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
