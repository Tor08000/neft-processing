"""Decision memory audit trail and export signatures.

Revision ID: 20291810_0097_decision_memory_audit
Revises: 20291790_0096_case_event_signatures, 20291800_0095_audit_exports_storage
Create Date: 2025-03-18 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.alembic.helpers import column_exists, create_index_if_not_exists, create_table_if_not_exists, table_exists
from app.db.schema import resolve_db_schema


revision = "20291810_0097_decision_memory_audit"
down_revision = ("20291790_0096_case_event_signatures", "20291800_0095_audit_exports_storage")
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def _schema_prefix() -> str:
    return f"{SCHEMA}." if SCHEMA else ""


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_not_exists(
        bind,
        "decision_memory",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True),
        sa.Column("decision_type", sa.String(length=32), nullable=False),
        sa.Column("decision_ref_id", sa.String(length=36), nullable=False),
        sa.Column("decision_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("score_snapshot", sa.JSON(), nullable=True),
        sa.Column("mastery_snapshot", sa.JSON(), nullable=True),
        sa.Column("audit_event_id", sa.String(length=36), sa.ForeignKey("case_events.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_decision_memory_case_at",
        "decision_memory",
        ["case_id", "decision_at"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_decision_memory_audit_event",
        "decision_memory",
        ["audit_event_id"],
        schema=SCHEMA,
    )

    if table_exists(bind, "case_exports", schema=SCHEMA):
        table_name = "case_exports"
        if not column_exists(bind, table_name, "artifact_signature", schema=SCHEMA):
            op.add_column(table_name, sa.Column("artifact_signature", sa.Text(), nullable=True), schema=SCHEMA)
        if not column_exists(bind, table_name, "artifact_signature_alg", schema=SCHEMA):
            op.add_column(table_name, sa.Column("artifact_signature_alg", sa.String(length=64), nullable=True), schema=SCHEMA)
        if not column_exists(bind, table_name, "artifact_signing_key_id", schema=SCHEMA):
            op.add_column(
                table_name,
                sa.Column("artifact_signing_key_id", sa.String(length=256), nullable=True),
                schema=SCHEMA,
            )
        if not column_exists(bind, table_name, "artifact_signed_at", schema=SCHEMA):
            op.add_column(
                table_name,
                sa.Column("artifact_signed_at", sa.DateTime(timezone=True), nullable=True),
                schema=SCHEMA,
            )

    if table_exists(bind, "decision_memory", schema=SCHEMA):
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_schema_prefix()}decision_memory_worm_guard()
                RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'decision_memory is WORM';
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS decision_memory_worm_update ON {_schema_prefix()}decision_memory;
                CREATE TRIGGER decision_memory_worm_update
                BEFORE UPDATE ON {_schema_prefix()}decision_memory
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}decision_memory_worm_guard();
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS decision_memory_worm_delete ON {_schema_prefix()}decision_memory;
                CREATE TRIGGER decision_memory_worm_delete
                BEFORE DELETE ON {_schema_prefix()}decision_memory
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}decision_memory_worm_guard();
                """
            )
        )


def downgrade() -> None:
    pass
