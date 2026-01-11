"""Legal documents registry and acceptances.

Revision ID: 20297170_0125_legal_docs_registry
Revises: 20297160_0124_fix_operations_client_id_type
Create Date: 2029-08-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from app.alembic.utils import (
    SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    is_postgres,
    safe_enum,
)
from app.db.types import GUID


revision = "20297170_0125_legal_docs_registry"
down_revision = "20297160_0124_fix_operations_client_id_type"
branch_labels = None
depends_on = None


DOC_STATUS = ["DRAFT", "PUBLISHED", "ARCHIVED"]
CONTENT_TYPES = ["MARKDOWN", "HTML", "PLAIN"]
SUBJECT_TYPES = ["USER", "CLIENT", "PARTNER"]

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def _schema_prefix() -> str:
    return f"{SCHEMA}." if SCHEMA else ""


def _create_worm_trigger(table_name: str) -> None:
    if not is_postgres(op.get_bind()):
        return
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {_schema_prefix()}{table_name}_worm_guard()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION '{table_name} is WORM';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            DROP TRIGGER IF EXISTS {table_name}_worm_update
            ON {_schema_prefix()}{table_name}
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {table_name}_worm_update
            BEFORE UPDATE ON {_schema_prefix()}{table_name}
            FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}{table_name}_worm_guard()
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            DROP TRIGGER IF EXISTS {table_name}_worm_delete
            ON {_schema_prefix()}{table_name}
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {table_name}_worm_delete
            BEFORE DELETE ON {_schema_prefix()}{table_name}
            FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}{table_name}_worm_guard()
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "legal_document_status", DOC_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "legal_document_content_type", CONTENT_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "legal_subject_type", SUBJECT_TYPES, schema=SCHEMA)

    status_enum = safe_enum(bind, "legal_document_status", DOC_STATUS, schema=SCHEMA)
    content_enum = safe_enum(bind, "legal_document_content_type", CONTENT_TYPES, schema=SCHEMA)
    subject_enum = safe_enum(bind, "legal_subject_type", SUBJECT_TYPES, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "legal_documents",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False, server_default="ru"),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("content_type", content_enum, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        schema=SCHEMA,
    )

    create_unique_index_if_not_exists(
        bind,
        "uq_legal_documents_code_version_locale",
        "legal_documents",
        ["code", "version", "locale"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_legal_documents_code_status",
        "legal_documents",
        ["code", "status"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_legal_documents_effective_from",
        "legal_documents",
        ["effective_from"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "legal_acceptances",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("subject_type", subject_enum, nullable=False),
        sa.Column("subject_id", sa.String(length=64), nullable=False),
        sa.Column("document_code", sa.String(length=64), nullable=False),
        sa.Column("document_version", sa.String(length=32), nullable=False),
        sa.Column("document_locale", sa.String(length=8), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("acceptance_hash", sa.String(length=64), nullable=False),
        sa.Column("signature", JSON_TYPE, nullable=True),
        sa.Column("meta", JSON_TYPE, nullable=True),
        schema=SCHEMA,
    )

    create_unique_index_if_not_exists(
        bind,
        "uq_legal_acceptances_subject_doc",
        "legal_acceptances",
        ["subject_type", "subject_id", "document_code", "document_version", "document_locale"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_legal_acceptances_subject",
        "legal_acceptances",
        ["subject_type", "subject_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_legal_acceptances_doc",
        "legal_acceptances",
        ["document_code", "document_version"],
        schema=SCHEMA,
    )

    _create_worm_trigger("legal_acceptances")


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
