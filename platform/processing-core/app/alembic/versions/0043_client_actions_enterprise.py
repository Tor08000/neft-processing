"""Harden client actions schema and add audit visibility.

Revision ID: 0043_client_actions_enterprise
Revises: 20280315_0042_client_actions_v1
Create Date: 2028-03-20 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import column_exists, ensure_pg_enum, ensure_pg_enum_value, is_postgres, safe_enum
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "0043_client_actions_enterprise"
down_revision = "20280315_0042_client_actions_v1"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

RECONCILIATION_STATUSES = [
    "REQUESTED",
    "IN_PROGRESS",
    "GENERATED",
    "SENT",
    "ACKNOWLEDGED",
    "REJECTED",
    "CANCELLED",
]
INVOICE_THREAD_STATUSES = ["OPEN", "WAITING_SUPPORT", "WAITING_CLIENT", "RESOLVED", "CLOSED"]
INVOICE_MESSAGE_SENDERS = ["CLIENT", "SUPPORT", "SYSTEM"]
AUDIT_VISIBILITY = ["PUBLIC", "INTERNAL"]


def _qualify(name: str) -> str:
    if SCHEMA and SCHEMA not in {"public"}:
        return f"{SCHEMA}.{name}"
    return name


def _enum_value_exists(bind, enum_name: str, value: str) -> bool:
    if not is_postgres(bind):
        return False
    schema = SCHEMA or resolve_db_schema().schema
    return (
        bind.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                JOIN pg_enum e ON e.enumtypid = t.oid
                WHERE n.nspname = :schema
                  AND t.typname = :enum_name
                  AND e.enumlabel = :value
                LIMIT 1
                """
            ),
            {"schema": schema, "enum_name": enum_name, "value": value},
        ).scalar()
        is not None
    )


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "audit_visibility", AUDIT_VISIBILITY, schema=SCHEMA)
    ensure_pg_enum(bind, "reconciliation_request_status", RECONCILIATION_STATUSES, schema=SCHEMA)
    ensure_pg_enum(bind, "invoice_thread_status", INVOICE_THREAD_STATUSES, schema=SCHEMA)
    ensure_pg_enum(bind, "invoice_message_sender_type", INVOICE_MESSAGE_SENDERS, schema=SCHEMA)

    if is_postgres(bind):
        enum_schema = SCHEMA or resolve_db_schema().schema
        for value in AUDIT_VISIBILITY:
            ensure_pg_enum_value(bind, "audit_visibility", value, schema=enum_schema)
        for value in RECONCILIATION_STATUSES:
            ensure_pg_enum_value(bind, "reconciliation_request_status", value, schema=enum_schema)
        for value in INVOICE_THREAD_STATUSES:
            ensure_pg_enum_value(bind, "invoice_thread_status", value, schema=enum_schema)
        for value in INVOICE_MESSAGE_SENDERS:
            ensure_pg_enum_value(bind, "invoice_message_sender_type", value, schema=enum_schema)

    if not column_exists(bind, "audit_log", "visibility", schema=SCHEMA):
        visibility_enum = safe_enum(bind, "audit_visibility", AUDIT_VISIBILITY, schema=SCHEMA)
        op.add_column(
            "audit_log",
            sa.Column("visibility", visibility_enum, nullable=True),
            schema=SCHEMA,
        )
        op.execute(sa.text(f"UPDATE {_qualify('audit_log')} SET visibility='INTERNAL' WHERE visibility IS NULL"))
        op.alter_column(
            "audit_log",
            "visibility",
            nullable=False,
            server_default="INTERNAL",
            schema=SCHEMA,
        )

    if column_exists(bind, "reconciliation_requests", "status", schema=SCHEMA):
        if _enum_value_exists(bind, "reconciliation_request_status", "NEW"):
            op.execute(
                sa.text(
                    f"UPDATE {_qualify('reconciliation_requests')} SET status='REQUESTED' WHERE status='NEW'"
                )
            )
        if _enum_value_exists(bind, "reconciliation_request_status", "READY"):
            op.execute(
                sa.text(
                    f"UPDATE {_qualify('reconciliation_requests')} SET status='GENERATED' WHERE status='READY'"
                )
            )
        op.alter_column(
            "reconciliation_requests",
            "status",
            server_default="REQUESTED",
            schema=SCHEMA,
        )

    new_columns = {
        "requested_at": sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        "generated_at": sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        "sent_at": sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        "acknowledged_at": sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        "result_hash_sha256": sa.Column("result_hash_sha256", sa.String(length=64), nullable=True),
        "version": sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        "note_client": sa.Column("note_client", sa.Text(), nullable=True),
        "note_ops": sa.Column("note_ops", sa.Text(), nullable=True),
        "meta": sa.Column("meta", sa.JSON(), nullable=True),
    }
    for name, column in new_columns.items():
        if not column_exists(bind, "reconciliation_requests", name, schema=SCHEMA):
            op.add_column("reconciliation_requests", column, schema=SCHEMA)

    if column_exists(bind, "reconciliation_requests", "note", schema=SCHEMA) and column_exists(
        bind, "reconciliation_requests", "note_client", schema=SCHEMA
    ):
        op.execute(
            sa.text(
                f"UPDATE {_qualify('reconciliation_requests')} SET note_client=note WHERE note_client IS NULL"
            )
        )
        op.drop_column("reconciliation_requests", "note", schema=SCHEMA)

    if column_exists(bind, "reconciliation_requests", "requested_at", schema=SCHEMA):
        op.execute(
            sa.text(
                f"UPDATE {_qualify('reconciliation_requests')} SET requested_at=created_at WHERE requested_at IS NULL"
            )
        )
        op.alter_column(
            "reconciliation_requests",
            "requested_at",
            nullable=False,
            schema=SCHEMA,
        )

    doc_columns = {
        "document_object_key": sa.Column("document_object_key", sa.Text(), nullable=True),
        "document_hash": sa.Column("document_hash", sa.String(length=64), nullable=True),
        "ack_ip": sa.Column("ack_ip", sa.Text(), nullable=True),
        "ack_user_agent": sa.Column("ack_user_agent", sa.Text(), nullable=True),
        "ack_method": sa.Column("ack_method", sa.String(length=32), nullable=True),
    }
    for name, column in doc_columns.items():
        if not column_exists(bind, "document_acknowledgements", name, schema=SCHEMA):
            op.add_column("document_acknowledgements", column, schema=SCHEMA)

    if is_postgres(bind):
        function_name = _qualify("audit_log_immutable")
        table_name = _qualify("audit_log")
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'audit_log is immutable';
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        trigger_name = "trg_audit_log_immutable"
        op.execute(
            sa.text(
                f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_trigger WHERE tgname = '{trigger_name}'
                    ) THEN
                        CREATE TRIGGER {trigger_name}
                        BEFORE UPDATE OR DELETE ON {table_name}
                        FOR EACH ROW EXECUTE FUNCTION {function_name}();
                    END IF;
                END$$;
                """
            )
        )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
