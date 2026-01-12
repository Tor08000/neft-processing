"""money flow v2 core tables

Revision ID: 20291510_0070_money_flow_v2
Revises: 20291501_0069_fuel_antifraud_v3
Create Date: 2029-05-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import create_table_if_not_exists, ensure_pg_enum, table_exists
from db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20291510_0070_money_flow_v2"
down_revision = "20291501_0069_fuel_antifraud_v3"
branch_labels = None
depends_on = None

MONEY_FLOW_STATE = [
    "DRAFT",
    "AUTHORIZED",
    "PENDING_SETTLEMENT",
    "SETTLED",
    "REVERSED",
    "DISPUTED",
    "FAILED",
    "CANCELLED",
]

MONEY_FLOW_TYPE = [
    "FUEL_TX",
    "SUBSCRIPTION_CHARGE",
    "INVOICE_PAYMENT",
    "REFUND",
    "PAYOUT",
]

MONEY_FLOW_EVENT_TYPE = [
    "AUTHORIZE",
    "SETTLE",
    "REVERSE",
    "DISPUTE_OPEN",
    "DISPUTE_RESOLVE",
    "FAIL",
    "CANCEL",
]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "money_flow_state", MONEY_FLOW_STATE, schema=SCHEMA)
    ensure_pg_enum(bind, "money_flow_type", MONEY_FLOW_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "money_flow_event_type", MONEY_FLOW_EVENT_TYPE, schema=SCHEMA)

    if not table_exists(bind, "money_flow_events", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "money_flow_events",
            schema=SCHEMA,
            columns=(
                sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
                sa.Column("tenant_id", sa.Integer, nullable=False),
                sa.Column("client_id", sa.String(64), nullable=False),
                sa.Column(
                    "flow_type",
                    postgresql.ENUM(
                        *MONEY_FLOW_TYPE,
                        name="money_flow_type",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("flow_ref_id", sa.String(64), nullable=False),
                sa.Column(
                    "state_from",
                    postgresql.ENUM(
                        *MONEY_FLOW_STATE,
                        name="money_flow_state",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=True,
                ),
                sa.Column(
                    "state_to",
                    postgresql.ENUM(
                        *MONEY_FLOW_STATE,
                        name="money_flow_state",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column(
                    "event_type",
                    postgresql.ENUM(
                        *MONEY_FLOW_EVENT_TYPE,
                        name="money_flow_event_type",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("idempotency_key", sa.String(128), nullable=False),
                sa.Column("ledger_transaction_id", postgresql.UUID(as_uuid=False), nullable=True),
                sa.Column("risk_decision_id", postgresql.UUID(as_uuid=False), nullable=True),
                sa.Column("reason_code", sa.String(128), nullable=True),
                sa.Column("explain_snapshot", sa.JSON, nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("meta", sa.JSON, nullable=True),
                sa.PrimaryKeyConstraint("id"),
            ),
        )
        op.create_index(
            "ix_money_flow_events_flow_ref",
            "money_flow_events",
            ["flow_type", "flow_ref_id"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_money_flow_events_state",
            "money_flow_events",
            ["state_to"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_money_flow_events_ledger_tx",
            "money_flow_events",
            ["ledger_transaction_id"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_money_flow_events_risk_decision",
            "money_flow_events",
            ["risk_decision_id"],
            schema=SCHEMA,
        )
        op.create_unique_constraint(
            "uq_money_flow_events_idempotency",
            "money_flow_events",
            ["idempotency_key"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    pass
