"""ops escalations

Revision ID: 20291530_0075_ops_escalations
Revises: 20291520_0074_logistics_navigator_core
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, table_exists
from db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20291530_0075_ops_escalations"
down_revision = "20291520_0074_logistics_navigator_core"
branch_labels = None
depends_on = None

OPS_ESCALATION_TARGET = ["CRM", "COMPLIANCE", "LOGISTICS", "FINANCE"]
OPS_ESCALATION_STATUS = ["OPEN", "ACK", "CLOSED"]
OPS_ESCALATION_PRIORITY = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
OPS_ESCALATION_SOURCE = ["AUTO_SLA_EXPIRED", "MANUAL_FROM_EXPLAIN", "SYSTEM"]
OPS_ESCALATION_PRIMARY_REASON = ["LIMIT", "RISK", "LOGISTICS", "MONEY", "POLICY", "UNKNOWN"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "ops_escalation_target", OPS_ESCALATION_TARGET, schema=SCHEMA)
    ensure_pg_enum(bind, "ops_escalation_status", OPS_ESCALATION_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "ops_escalation_priority", OPS_ESCALATION_PRIORITY, schema=SCHEMA)
    ensure_pg_enum(bind, "ops_escalation_source", OPS_ESCALATION_SOURCE, schema=SCHEMA)
    ensure_pg_enum(bind, "ops_escalation_primary_reason", OPS_ESCALATION_PRIMARY_REASON, schema=SCHEMA)

    if not table_exists(bind, "ops_escalations", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "ops_escalations",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(36), primary_key=True),
                sa.Column("tenant_id", sa.Integer, nullable=False),
                sa.Column("client_id", sa.String(length=64), nullable=True),
                sa.Column(
                    "target",
                    postgresql.ENUM(
                        *OPS_ESCALATION_TARGET,
                        name="ops_escalation_target",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column(
                    "status",
                    postgresql.ENUM(
                        *OPS_ESCALATION_STATUS,
                        name="ops_escalation_status",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                    server_default="OPEN",
                ),
                sa.Column(
                    "priority",
                    postgresql.ENUM(
                        *OPS_ESCALATION_PRIORITY,
                        name="ops_escalation_priority",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                    server_default="MEDIUM",
                ),
                sa.Column(
                    "primary_reason",
                    postgresql.ENUM(
                        *OPS_ESCALATION_PRIMARY_REASON,
                        name="ops_escalation_primary_reason",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("subject_type", sa.String(length=64), nullable=False),
                sa.Column("subject_id", sa.String(length=128), nullable=False),
                sa.Column(
                    "source",
                    postgresql.ENUM(
                        *OPS_ESCALATION_SOURCE,
                        name="ops_escalation_source",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("sla_started_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("sla_expires_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("created_by_actor_type", sa.String(length=32), nullable=True),
                sa.Column("created_by_actor_id", sa.String(length=64), nullable=True),
                sa.Column("created_by_actor_email", sa.String(length=128), nullable=True),
                sa.Column("meta", sa.JSON(), nullable=True),
                sa.Column("idempotency_key", sa.String(length=128), nullable=False, unique=True),
                sa.PrimaryKeyConstraint("id"),
            ),
        )
        create_index_if_not_exists(bind, "ix_ops_escalations_tenant", "ops_escalations", ["tenant_id"], schema=SCHEMA)
        create_index_if_not_exists(
            bind, "ix_ops_escalations_target_status", "ops_escalations", ["target", "status"], schema=SCHEMA
        )
        create_index_if_not_exists(bind, "ix_ops_escalations_client", "ops_escalations", ["client_id"], schema=SCHEMA)
        create_index_if_not_exists(
            bind, "ix_ops_escalations_subject", "ops_escalations", ["subject_type", "subject_id"], schema=SCHEMA
        )
        create_index_if_not_exists(
            bind, "ix_ops_escalations_created_at", "ops_escalations", ["created_at"], schema=SCHEMA
        )


def downgrade() -> None:
    pass
