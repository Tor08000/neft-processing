"""Add legal gate documents and acceptances.

Revision ID: 20297200_0125_add_legal_gate_tables
Revises: 20297170_0125_legal_docs_registry
Create Date: 2029-08-10 00:00:00.000000
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.helpers import is_postgres
from app.alembic.utils import (
    SCHEMA,
    column_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)

revision = "20297200_0125_add_legal_gate_tables"
down_revision = "20297170_0125_legal_docs_registry"
branch_labels = None
depends_on = None


LEGAL_DOCUMENT_STATUS = ["DRAFT", "PUBLISHED", "ARCHIVED"]
LEGAL_SUBJECT_TYPE = ["CLIENT", "PARTNER", "USER"]


def _ensure_schema() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return
    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))


def _uuid_type(bind: sa.engine.Connection) -> sa.types.TypeEngine:
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def _columns_exist(
    bind: sa.engine.Connection, table_name: str, columns: list[str], schema: str
) -> bool:
    return all(column_exists(bind, table_name, column, schema=schema) for column in columns)


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_schema()

    ensure_pg_enum(bind, "legal_document_status", LEGAL_DOCUMENT_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "legal_subject_type", LEGAL_SUBJECT_TYPE, schema=SCHEMA)

    status_enum = safe_enum(bind, "legal_document_status", LEGAL_DOCUMENT_STATUS, schema=SCHEMA)
    subject_enum = safe_enum(bind, "legal_subject_type", LEGAL_SUBJECT_TYPE, schema=SCHEMA)
    uuid_type = _uuid_type(bind)

    create_table_if_not_exists(
        bind,
        "legal_documents",
        sa.Column("id", uuid_type, primary_key=True, nullable=False, default=uuid.uuid4),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", status_enum, nullable=False, server_default="DRAFT"),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("code", "version", name="uq_legal_documents_code_version"),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "legal_acceptances",
        sa.Column("id", uuid_type, primary_key=True, nullable=False, default=uuid.uuid4),
        sa.Column("document_id", uuid_type, sa.ForeignKey(f"{SCHEMA}.legal_documents.id"), nullable=False),
        sa.Column("subject_type", subject_enum, nullable=False),
        sa.Column("subject_id", sa.Text(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "subject_type", "subject_id", "document_id", name="uq_legal_acceptances_scope"
        ),
        schema=SCHEMA,
    )

    for index_name, table, columns in [
        ("ix_legal_documents_code", "legal_documents", ["code"]),
        ("ix_legal_documents_status", "legal_documents", ["status"]),
        ("ix_legal_documents_effective_from", "legal_documents", ["effective_from"]),
        ("ix_legal_acceptances_document_id", "legal_acceptances", ["document_id"]),
        ("ix_legal_acceptances_doc", "legal_acceptances", ["document_code", "document_version"]),
        ("ix_legal_acceptances_subject_type", "legal_acceptances", ["subject_type"]),
        ("ix_legal_acceptances_subject_id", "legal_acceptances", ["subject_id"]),
    ]:
        if not _columns_exist(bind, table, columns, schema=SCHEMA):
            continue
        create_index_if_not_exists(bind, index_name, table, columns, schema=SCHEMA)


def downgrade() -> None:
    raise RuntimeError("legal gate tables cannot be safely downgraded")
