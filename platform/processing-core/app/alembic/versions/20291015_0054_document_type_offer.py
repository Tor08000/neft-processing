"""Add OFFER document type.

Revision ID: 20291015_0054_document_type_offer
Revises: 20291010_0053_risk_engine_v5
Create Date: 2029-10-15 00:00:00
"""

from __future__ import annotations

from alembic import op

from app.alembic.helpers import ensure_pg_enum_value, is_postgres
from app.db.schema import resolve_db_schema


# revision identifiers, used by Alembic.
revision = "20291015_0054_document_type_offer"
down_revision = "20291010_0053_risk_engine_v5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return
    schema = resolve_db_schema().schema
    ensure_pg_enum_value(bind, "document_type", "OFFER", schema=schema)


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
