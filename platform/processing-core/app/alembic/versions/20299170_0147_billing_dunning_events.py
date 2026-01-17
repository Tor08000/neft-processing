"""Billing dunning events.

Revision ID: 20299170_0147_billing_dunning_events
Revises: 20299160_0146_pricing_catalog_usage_meter
Create Date: 2026-02-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import (
    SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)


revision = "20299170_0147_billing_dunning_events"
down_revision = "20299160_0146_pricing_catalog_usage_meter"
branch_labels = None
depends_on = None


DUNNING_EVENT_TYPES = [
    "DUE_SOON_7D",
    "DUE_SOON_1D",
    "OVERDUE_1D",
    "OVERDUE_7D",
    "PRE_SUSPEND_1D",
    "SUSPENDED",
]
DUNNING_CHANNELS = ["EMAIL", "IN_APP"]
DUNNING_STATUSES = ["SENT", "FAILED", "SKIPPED"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "billing_dunning_event_type", DUNNING_EVENT_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "billing_dunning_channel", DUNNING_CHANNELS, schema=SCHEMA)
    ensure_pg_enum(bind, "billing_dunning_status", DUNNING_STATUSES, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "billing_dunning_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("invoice_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "event_type",
            safe_enum(bind, "billing_dunning_event_type", DUNNING_EVENT_TYPES, schema=SCHEMA),
            nullable=False,
        ),
        sa.Column(
            "channel",
            safe_enum(bind, "billing_dunning_channel", DUNNING_CHANNELS, schema=SCHEMA),
            nullable=False,
        ),
        sa.Column(
            "status",
            safe_enum(bind, "billing_dunning_status", DUNNING_STATUSES, schema=SCHEMA),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_billing_dunning_events_idempotency",
        "billing_dunning_events",
        ["idempotency_key"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_billing_dunning_events_org",
        "billing_dunning_events",
        ["org_id", "sent_at"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_billing_dunning_events_invoice",
        "billing_dunning_events",
        ["invoice_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_billing_dunning_events_channel",
        "billing_dunning_events",
        ["channel", "status"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_billing_dunning_events_channel", table_name="billing_dunning_events", schema=SCHEMA)
    op.drop_index("ix_billing_dunning_events_invoice", table_name="billing_dunning_events", schema=SCHEMA)
    op.drop_index("ix_billing_dunning_events_org", table_name="billing_dunning_events", schema=SCHEMA)
    op.drop_index("uq_billing_dunning_events_idempotency", table_name="billing_dunning_events", schema=SCHEMA)
    op.drop_table("billing_dunning_events", schema=SCHEMA)
