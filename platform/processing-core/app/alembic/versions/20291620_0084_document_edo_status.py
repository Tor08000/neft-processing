"""Add document EDO status tracking.

Revision ID: 20291620_0084_document_edo_status
Revises: 20291610_0083_document_signature_chain
Create Date: 2029-16-20 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from alembic_helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)
from db.schema import resolve_db_schema

revision = "20291620_0084_document_edo_status"
down_revision = "20291610_0083_document_signature_chain"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

EDO_PROVIDER = ["DIADOK", "SBIS"]
EDO_DOCUMENT_STATUS = [
    "QUEUED",
    "UPLOADING",
    "SENT",
    "DELIVERED",
    "SIGNED_BY_US",
    "SIGNED_BY_COUNTERPARTY",
    "REJECTED",
    "FAILED",
]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "edo_provider", EDO_PROVIDER, schema=SCHEMA)
    ensure_pg_enum(bind, "edo_document_status", EDO_DOCUMENT_STATUS, schema=SCHEMA)

    provider_enum = safe_enum(bind, "edo_provider", EDO_PROVIDER, schema=SCHEMA)
    status_enum = safe_enum(bind, "edo_document_status", EDO_DOCUMENT_STATUS, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "document_edo_status",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("signature_id", sa.String(length=36), nullable=True),
        sa.Column("provider", provider_enum, nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("provider_message_id", sa.String(length=128), nullable=True),
        sa.Column("provider_document_id", sa.String(length=128), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_status_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        schema=SCHEMA,
    )

    create_unique_index_if_not_exists(
        bind,
        "uq_document_edo_status_document_provider",
        "document_edo_status",
        ["document_id", "provider"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_document_edo_status_document_id",
        "document_edo_status",
        ["document_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_document_edo_status_status",
        "document_edo_status",
        ["status"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    pass
