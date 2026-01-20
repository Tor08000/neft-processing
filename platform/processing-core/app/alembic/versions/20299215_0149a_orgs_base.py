"""Create orgs base table.

Revision ID: 20299215_0149a_orgs_base
Revises: 20299210_0149_bank_statement_imports
Create Date: 2026-02-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import DB_SCHEMA, create_table_if_not_exists, table_exists


revision = "20299215_0149a_orgs_base"
down_revision = "20299210_0149_bank_statement_imports"
branch_labels = None
depends_on = None


def _json_type(bind: sa.engine.Connection):
    return postgresql.JSONB(none_as_null=True) if bind.dialect.name == "postgresql" else sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, "orgs", schema=DB_SCHEMA):
        return

    create_table_if_not_exists(
        bind,
        "orgs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("roles", _json_type(bind), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        schema=DB_SCHEMA,
    )



def downgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, "orgs", schema=DB_SCHEMA):
        op.drop_table("orgs", schema=DB_SCHEMA)
