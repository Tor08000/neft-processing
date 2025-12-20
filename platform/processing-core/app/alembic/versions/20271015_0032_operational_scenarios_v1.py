"""Operational scenarios v1: refunds, reversals, disputes, adjustments

Revision ID: 20271015_0032_operational_scenarios_v1
Revises: 20270901_0031_partner_settlements
Create Date: 2027-10-15 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_table_if_exists,
    ensure_pg_enum,
    safe_enum,
)
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20271015_0032_operational_scenarios_v1"
down_revision = "20270901_0031_partner_settlements"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

REFUND_STATUS = ["REQUESTED", "POSTED", "FAILED", "CANCELLED"]
SETTLEMENT_POLICY = ["SAME_PERIOD", "ADJUSTMENT_REQUIRED"]
REVERSAL_STATUS = ["REQUESTED", "POSTED", "FAILED", "CANCELLED"]
DISPUTE_STATUS = ["OPEN", "UNDER_REVIEW", "ACCEPTED", "REJECTED", "CLOSED"]
DISPUTE_EVENT_TYPES = [
    "OPENED",
    "MOVED_TO_REVIEW",
    "ACCEPTED",
    "REJECTED",
    "CLOSED",
    "HOLD_PLACED",
    "HOLD_RELEASED",
    "REFUND_POSTED",
    "FEE_POSTED",
]
ADJUSTMENT_KIND = ["REFUND_ADJUSTMENT", "REVERSAL_ADJUSTMENT", "DISPUTE_ADJUSTMENT", "FEE_ADJUSTMENT"]
ADJUSTMENT_RELATED = ["REFUND", "REVERSAL", "DISPUTE"]
ADJUSTMENT_STATUS = ["PENDING", "POSTED", "FAILED"]
POSTING_BATCH_NEW_VALUES = ["DISPUTE_HOLD", "DISPUTE_RELEASE"]


def _uuid_type(bind):
    return sa.String(length=36) if getattr(getattr(bind, "dialect", None), "name", None) == "sqlite" else sa.dialects.postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "refund_request_status", REFUND_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "settlement_policy", SETTLEMENT_POLICY, schema=SCHEMA)
    ensure_pg_enum(bind, "reversal_status", REVERSAL_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "dispute_status", DISPUTE_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "dispute_event_type", DISPUTE_EVENT_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "financial_adjustment_kind", ADJUSTMENT_KIND, schema=SCHEMA)
    ensure_pg_enum(bind, "financial_adjustment_related", ADJUSTMENT_RELATED, schema=SCHEMA)
    ensure_pg_enum(bind, "financial_adjustment_status", ADJUSTMENT_STATUS, schema=SCHEMA)
    if getattr(getattr(bind, "dialect", None), "name", None) == "postgresql":
        for value in POSTING_BATCH_NEW_VALUES:
            op.execute(
                sa.text(
                    "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                    "JOIN pg_namespace n ON n.oid = t.typnamespace WHERE t.typname = :name AND e.enumlabel = :value "
                    "AND n.nspname = :schema) THEN "
                    "ALTER TYPE {schema}.postingbatchtype ADD VALUE :value; END IF; END $$;".format(
                        schema=SCHEMA or "public"
                    )
                ),
                {"name": "postingbatchtype", "value": value, "schema": SCHEMA or "public"},
            )

    refund_status = safe_enum(bind, "refund_request_status", REFUND_STATUS, schema=SCHEMA)
    settlement_policy = safe_enum(bind, "settlement_policy", SETTLEMENT_POLICY, schema=SCHEMA)
    reversal_status = safe_enum(bind, "reversal_status", REVERSAL_STATUS, schema=SCHEMA)
    dispute_status = safe_enum(bind, "dispute_status", DISPUTE_STATUS, schema=SCHEMA)
    dispute_event_type = safe_enum(bind, "dispute_event_type", DISPUTE_EVENT_TYPES, schema=SCHEMA)
    adjustment_kind = safe_enum(bind, "financial_adjustment_kind", ADJUSTMENT_KIND, schema=SCHEMA)
    adjustment_related = safe_enum(bind, "financial_adjustment_related", ADJUSTMENT_RELATED, schema=SCHEMA)
    adjustment_status = safe_enum(bind, "financial_adjustment_status", ADJUSTMENT_STATUS, schema=SCHEMA)

    operation_fk = "operations.id" if not SCHEMA else f"{SCHEMA}.operations.id"
    dispute_fk = "disputes.id" if not SCHEMA else f"{SCHEMA}.disputes.id"

    create_table_if_not_exists(
        bind,
        "refund_requests",
        sa.Column("id", _uuid_type(bind), primary_key=True),
        sa.Column("operation_id", _uuid_type(bind), sa.ForeignKey(operation_fk, ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("operation_business_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("amount", sa.BigInteger, nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("initiator", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False, unique=True),
        sa.Column("status", refund_status, nullable=False, server_default=REFUND_STATUS[0], index=True),
        sa.Column("posted_posting_id", _uuid_type(bind), nullable=True),
        sa.Column("settlement_policy", settlement_policy, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "reversals",
        sa.Column("id", _uuid_type(bind), primary_key=True),
        sa.Column("operation_id", _uuid_type(bind), sa.ForeignKey(operation_fk, ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("operation_business_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("initiator", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False, unique=True),
        sa.Column("status", reversal_status, nullable=False, server_default=REVERSAL_STATUS[0], index=True),
        sa.Column("posted_posting_id", _uuid_type(bind), nullable=True),
        sa.Column("settlement_policy", settlement_policy, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "disputes",
        sa.Column("id", _uuid_type(bind), primary_key=True),
        sa.Column("operation_id", _uuid_type(bind), sa.ForeignKey(operation_fk, ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("operation_business_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("disputed_amount", sa.BigInteger, nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("fee_amount", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("status", dispute_status, nullable=False, server_default=DISPUTE_STATUS[0], index=True),
        sa.Column("hold_placed", sa.Boolean, nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("hold_posting_id", _uuid_type(bind), nullable=True),
        sa.Column("resolution_posting_id", _uuid_type(bind), nullable=True),
        sa.Column("initiator", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_disputes_operation_id", "disputes", ["operation_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_disputes_status", "disputes", ["status"], schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "dispute_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("dispute_id", _uuid_type(bind), sa.ForeignKey(dispute_fk, ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("event_type", dispute_event_type, nullable=False),
        sa.Column("payload", sa.JSON, nullable=True),
        sa.Column("actor", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_dispute_events_dispute_id_created_at", "dispute_events", ["dispute_id", "created_at"], schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "financial_adjustments",
        sa.Column("id", _uuid_type(bind), primary_key=True),
        sa.Column("kind", adjustment_kind, nullable=False),
        sa.Column("related_entity_type", adjustment_related, nullable=False),
        sa.Column("related_entity_id", _uuid_type(bind), nullable=False),
        sa.Column("operation_id", _uuid_type(bind), sa.ForeignKey(operation_fk, ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("amount", sa.BigInteger, nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", adjustment_status, nullable=False, server_default=ADJUSTMENT_STATUS[0], index=True),
        sa.Column("posting_id", _uuid_type(bind), nullable=True),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()
    drop_table_if_exists(bind, "financial_adjustments", schema=SCHEMA)
    drop_table_if_exists(bind, "dispute_events", schema=SCHEMA)
    drop_table_if_exists(bind, "disputes", schema=SCHEMA)
    drop_table_if_exists(bind, "reversals", schema=SCHEMA)
    drop_table_if_exists(bind, "refund_requests", schema=SCHEMA)
