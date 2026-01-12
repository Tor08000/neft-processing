"""Add legal gate documents and acceptances.

Revision ID: 20297200_0125_add_legal_gate_tables
Revises: 20297170_0125_legal_docs_registry
Create Date: 2029-08-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from alembic_helpers import is_postgres
from alembic_helpers import (
    SCHEMA,
    column_exists,
    create_index_if_not_exists,
    ensure_pg_enum,
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


def _columns_exist(
    bind: sa.engine.Connection, table_name: str, columns: list[str], schema: str
) -> bool:
    return all(column_exists(bind, table_name, column, schema=schema) for column in columns)


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_schema()

    ensure_pg_enum(bind, "legal_document_status", LEGAL_DOCUMENT_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "legal_subject_type", LEGAL_SUBJECT_TYPE, schema=SCHEMA)

    for index_name, table, columns in [
        ("ix_legal_documents_code", "legal_documents", ["code"]),
        ("ix_legal_documents_status", "legal_documents", ["status"]),
        ("ix_legal_documents_effective_from", "legal_documents", ["effective_from"]),
        ("ix_legal_acceptances_doc", "legal_acceptances", ["document_code", "document_version"]),
        ("ix_legal_acceptances_document_id", "legal_acceptances", ["document_id"]),
        ("ix_legal_acceptances_subject_type", "legal_acceptances", ["subject_type"]),
        ("ix_legal_acceptances_subject_id", "legal_acceptances", ["subject_id"]),
    ]:
        if not _columns_exist(bind, table, columns, schema=SCHEMA):
            continue
        create_index_if_not_exists(bind, index_name, table, columns, schema=SCHEMA)


def downgrade() -> None:
    raise RuntimeError("legal gate tables cannot be safely downgraded")
