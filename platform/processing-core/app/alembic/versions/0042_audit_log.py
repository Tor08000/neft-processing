"""Add immutable audit log table.

Revision ID: 0042_audit_log
Revises: 20280301_0041_payout_exports_bank_format
Create Date: 2028-04-10 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "0042_audit_log"
down_revision = "20280301_0041_payout_exports_bank_format"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

ACTOR_TYPES = ["USER", "SERVICE", "SYSTEM"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "audit_actor_type", ACTOR_TYPES, schema=SCHEMA)
    actor_type_enum = safe_enum(bind, "audit_actor_type", ACTOR_TYPES, schema=SCHEMA)

    json_type = postgresql.JSONB(none_as_null=True) if bind.dialect.name == "postgresql" else sa.JSON()
    ip_type = postgresql.INET() if bind.dialect.name == "postgresql" else sa.String(length=64)
    roles_type = postgresql.ARRAY(sa.String()) if bind.dialect.name == "postgresql" else sa.JSON()

    create_table_if_not_exists(
        bind,
        "audit_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("actor_type", actor_type_enum, nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("actor_email", sa.Text(), nullable=True),
        sa.Column("actor_roles", roles_type, nullable=True),
        sa.Column("ip", ip_type, nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.Text(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("before", json_type, nullable=True),
        sa.Column("after", json_type, nullable=True),
        sa.Column("diff", json_type, nullable=True),
        sa.Column("external_refs", json_type, nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("attachment_key", sa.Text(), nullable=True),
        sa.Column("prev_hash", sa.Text(), nullable=False),
        sa.Column("hash", sa.Text(), nullable=False, unique=True),
        schema=SCHEMA,
    )

    create_index_if_not_exists(bind, "ix_audit_log_ts_desc", "audit_log", ["ts"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_audit_log_event_ts", "audit_log", ["event_type", "ts"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_audit_log_tenant_ts", "audit_log", ["tenant_id", "ts"], schema=SCHEMA)
    create_index_if_not_exists(
        bind,
        "ix_audit_log_external_refs_gin",
        "audit_log",
        ["external_refs"],
        schema=SCHEMA,
        postgresql_using="gin",
    )

    if bind.dialect.name == "postgresql":
        schema_prefix = f"{SCHEMA}." if SCHEMA else ""
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION {schema_prefix}audit_log_immutable()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_log is immutable';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_log_immutable'
                ) THEN
                    CREATE TRIGGER trg_audit_log_immutable
                    BEFORE UPDATE OR DELETE ON {schema_prefix}audit_log
                    FOR EACH ROW
                    EXECUTE FUNCTION {schema_prefix}audit_log_immutable();
                END IF;
            END;
            $$;
            """
        )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
