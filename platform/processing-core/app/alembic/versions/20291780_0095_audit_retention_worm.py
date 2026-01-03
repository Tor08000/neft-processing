"""Audit retention tables and WORM guards.

Revision ID: 20291780_0095_audit_retention_worm
Revises: 20291770_0094_case_events_hash_chain
Create Date: 2025-03-12 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.alembic.helpers import create_index_if_not_exists, create_table_if_not_exists, table_exists
from app.db.schema import resolve_db_schema


revision = "20291780_0095_audit_retention_worm"
down_revision = "20291770_0094_case_events_hash_chain"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def _schema_prefix() -> str:
    return f"{SCHEMA}." if SCHEMA else ""


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_not_exists(
        bind,
        "audit_legal_holds",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_audit_legal_holds_active_case",
        "audit_legal_holds",
        ["active", "case_id"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "audit_purge_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=True),
        sa.Column("policy", sa.String(length=128), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("purged_by", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("prev_tail_hash", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_audit_purge_log_case_purged",
        "audit_purge_log",
        ["case_id", "purged_at"],
        schema=SCHEMA,
    )

    if table_exists(bind, "case_events", schema=SCHEMA):
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_schema_prefix()}case_events_worm_guard()
                RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'case_events is WORM';
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS case_events_worm_update ON {_schema_prefix()}case_events;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER case_events_worm_update
                BEFORE UPDATE ON {_schema_prefix()}case_events
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}case_events_worm_guard();
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS case_events_worm_delete ON {_schema_prefix()}case_events;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER case_events_worm_delete
                BEFORE DELETE ON {_schema_prefix()}case_events
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}case_events_worm_guard();
                """
            )
        )


def downgrade() -> None:
    pass
