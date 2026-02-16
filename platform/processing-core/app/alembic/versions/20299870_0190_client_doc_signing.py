"""Client generated docs signing workflow.

Revision ID: 20299870_0190_client_doc_signing
Revises: 20299860_0189_client_generated_documents
Create Date: 2026-02-16 00:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import DB_SCHEMA
from db.types import GUID

revision = "20299870_0190_client_doc_signing"
down_revision = "20299860_0189_client_generated_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("client_generated_documents", sa.Column("client_signed_at", sa.DateTime(timezone=True), nullable=True), schema=DB_SCHEMA)
    op.add_column("client_generated_documents", sa.Column("client_sign_method", sa.Text(), nullable=True), schema=DB_SCHEMA)
    op.add_column("client_generated_documents", sa.Column("client_sign_phone", sa.Text(), nullable=True), schema=DB_SCHEMA)
    op.add_column("client_generated_documents", sa.Column("client_signature_hash", sa.Text(), nullable=True), schema=DB_SCHEMA)
    op.add_column("client_generated_documents", sa.Column("platform_signed_at", sa.DateTime(timezone=True), nullable=True), schema=DB_SCHEMA)
    op.add_column("client_generated_documents", sa.Column("platform_signature_hash", sa.Text(), nullable=True), schema=DB_SCHEMA)
    op.create_index("ix_client_generated_documents_status", "client_generated_documents", ["status"], schema=DB_SCHEMA)
    op.create_index("ix_client_generated_documents_client_signed_at", "client_generated_documents", ["client_signed_at"], schema=DB_SCHEMA)

    op.create_table(
        "client_doc_sign_requests",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("doc_id", GUID(), sa.ForeignKey(f"{DB_SCHEMA}.client_generated_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("otp_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_ip", sa.Text(), nullable=True),
        sa.Column("request_user_agent", sa.Text(), nullable=True),
        schema=DB_SCHEMA,
    )
    op.create_index("ix_client_doc_sign_requests_doc_id", "client_doc_sign_requests", ["doc_id"], schema=DB_SCHEMA)
    op.create_index("ix_client_doc_sign_requests_status", "client_doc_sign_requests", ["status"], schema=DB_SCHEMA)
    op.create_index(
        "uq_client_doc_sign_requests_doc_pending",
        "client_doc_sign_requests",
        ["doc_id"],
        unique=True,
        schema=DB_SCHEMA,
        postgresql_where=sa.text("status = 'PENDING'"),
    )

    op.create_table(
        "client_audit_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("client_id", GUID(), nullable=True),
        sa.Column("application_id", GUID(), nullable=True),
        sa.Column("doc_id", GUID(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor_user_id", GUID(), nullable=True),
        sa.Column("actor_type", sa.Text(), nullable=True),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("meta_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    op.create_index("ix_client_audit_events_doc_id", "client_audit_events", ["doc_id"], schema=DB_SCHEMA)
    op.create_index("ix_client_audit_events_event_type", "client_audit_events", ["event_type"], schema=DB_SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_client_audit_events_event_type", table_name="client_audit_events", schema=DB_SCHEMA)
    op.drop_index("ix_client_audit_events_doc_id", table_name="client_audit_events", schema=DB_SCHEMA)
    op.drop_table("client_audit_events", schema=DB_SCHEMA)

    op.drop_index("uq_client_doc_sign_requests_doc_pending", table_name="client_doc_sign_requests", schema=DB_SCHEMA)
    op.drop_index("ix_client_doc_sign_requests_status", table_name="client_doc_sign_requests", schema=DB_SCHEMA)
    op.drop_index("ix_client_doc_sign_requests_doc_id", table_name="client_doc_sign_requests", schema=DB_SCHEMA)
    op.drop_table("client_doc_sign_requests", schema=DB_SCHEMA)

    op.drop_index("ix_client_generated_documents_client_signed_at", table_name="client_generated_documents", schema=DB_SCHEMA)
    op.drop_index("ix_client_generated_documents_status", table_name="client_generated_documents", schema=DB_SCHEMA)
    op.drop_column("client_generated_documents", "platform_signature_hash", schema=DB_SCHEMA)
    op.drop_column("client_generated_documents", "platform_signed_at", schema=DB_SCHEMA)
    op.drop_column("client_generated_documents", "client_signature_hash", schema=DB_SCHEMA)
    op.drop_column("client_generated_documents", "client_sign_phone", schema=DB_SCHEMA)
    op.drop_column("client_generated_documents", "client_sign_method", schema=DB_SCHEMA)
    op.drop_column("client_generated_documents", "client_signed_at", schema=DB_SCHEMA)
