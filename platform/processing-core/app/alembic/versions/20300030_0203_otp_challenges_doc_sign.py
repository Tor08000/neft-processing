"""OTP challenges for document signing.

Revision ID: 20300030_0203_otp_challenges_doc_sign
Revises: 20300020_0202_document_simple_signatures
Create Date: 2026-02-17 00:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import DB_SCHEMA
from db.types import GUID

revision = "20300030_0203_otp_challenges_doc_sign"
down_revision = "20300020_0202_document_simple_signatures"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "otp_challenges",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("purpose", sa.Text(), nullable=False, server_default="DOC_SIGN"),
        sa.Column("document_id", GUID(), sa.ForeignKey(f"{DB_SCHEMA}.client_generated_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("destination", sa.Text(), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("salt", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resend_available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_ip", sa.Text(), nullable=True),
        sa.Column("request_user_agent", sa.Text(), nullable=True),
        sa.Column("provider_message_id", sa.Text(), nullable=True),
        sa.Column("provider_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        schema=DB_SCHEMA,
    )
    op.create_index("ix_otp_challenges_user_id_created_at", "otp_challenges", ["user_id", "created_at"], schema=DB_SCHEMA)
    op.create_index("ix_otp_challenges_document_id", "otp_challenges", ["document_id"], schema=DB_SCHEMA)
    op.create_index(
        "uq_otp_challenges_active_document_user",
        "otp_challenges",
        ["document_id", "user_id"],
        unique=True,
        schema=DB_SCHEMA,
        postgresql_where=sa.text("status in ('PENDING','SENT','CONFIRMED')"),
    )


def downgrade() -> None:
    op.drop_index("uq_otp_challenges_active_document_user", table_name="otp_challenges", schema=DB_SCHEMA)
    op.drop_index("ix_otp_challenges_document_id", table_name="otp_challenges", schema=DB_SCHEMA)
    op.drop_index("ix_otp_challenges_user_id_created_at", table_name="otp_challenges", schema=DB_SCHEMA)
    op.drop_table("otp_challenges", schema=DB_SCHEMA)
