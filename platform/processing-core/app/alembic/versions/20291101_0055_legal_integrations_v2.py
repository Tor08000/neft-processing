"""Add legal integrations core tables.

Revision ID: 20291101_0055_legal_integrations_v2
Revises: 20291015_0054_document_type_offer
Create Date: 2029-11-01 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, ensure_pg_enum_value, safe_enum
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20291101_0055_legal_integrations_v2"
down_revision = "20291015_0054_document_type_offer"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

DOCUMENT_ENVELOPE_STATUS = ["CREATED", "SENT", "DELIVERED", "SIGNED", "DECLINED", "EXPIRED", "FAILED"]
SIGNATURE_TYPE = ["ESIGN", "KEP", "GOST_P7S", "EDI_SIGN"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "document_envelope_status", DOCUMENT_ENVELOPE_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "signature_type", SIGNATURE_TYPE, schema=SCHEMA)

    for value in ("SIG", "P7S", "CERT", "EDI_XML"):
        ensure_pg_enum_value(bind, "document_file_type", value, schema=SCHEMA or "public")

    envelope_status_enum = safe_enum(bind, "document_envelope_status", DOCUMENT_ENVELOPE_STATUS, schema=SCHEMA)
    signature_type_enum = safe_enum(bind, "signature_type", SIGNATURE_TYPE, schema=SCHEMA)

    documents_fk = "documents.id" if not SCHEMA else f"{SCHEMA}.documents.id"
    document_files_fk = "document_files.id" if not SCHEMA else f"{SCHEMA}.document_files.id"
    certificates_fk = "certificates.id" if not SCHEMA else f"{SCHEMA}.certificates.id"

    create_table_if_not_exists(
        bind,
        "document_envelopes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey(documents_fk), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("envelope_id", sa.String(length=128), nullable=False),
        sa.Column("status", envelope_status_enum, nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.UniqueConstraint("provider", "envelope_id", name="uq_document_envelopes_provider"),
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_document_envelopes_document", "document_envelopes", ["document_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_document_envelopes_status", "document_envelopes", ["status"], schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "certificates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("subject_dn", sa.Text(), nullable=True),
        sa.Column("issuer_dn", sa.Text(), nullable=True),
        sa.Column("serial_number", sa.Text(), nullable=True),
        sa.Column("thumbprint_sha256", sa.String(length=64), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("revocation_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_certificates_thumbprint", "certificates", ["thumbprint_sha256"], schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "document_signatures",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey(documents_fk), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("signature_type", signature_type_enum, nullable=False),
        sa.Column("file_id", sa.String(length=36), sa.ForeignKey(document_files_fk), nullable=True),
        sa.Column("signature_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("certificate_id", sa.String(length=36), sa.ForeignKey(certificates_fk), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("verification_details", sa.JSON(), nullable=True),
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_document_signatures_document", "document_signatures", ["document_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_document_signatures_provider", "document_signatures", ["provider"], schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "legal_provider_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("signing_provider", sa.String(length=64), nullable=False, server_default="none"),
        sa.Column("edo_provider", sa.String(length=64), nullable=False, server_default="none"),
        sa.Column("require_signature_for_finalize", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "client_id", name="uq_legal_provider_configs_scope"),
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_legal_provider_configs_tenant", "legal_provider_configs", ["tenant_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_legal_provider_configs_client", "legal_provider_configs", ["client_id"], schema=SCHEMA)


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
