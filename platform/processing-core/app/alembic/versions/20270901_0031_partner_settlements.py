"""Partner settlements and payout orders

Revision ID: 20270901_0031_partner_settlements
Revises: 20270831_0030_billing_state_machine
Create Date: 2024-09-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa

from alembic_helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_table_if_exists,
    ensure_pg_enum,
    is_sqlite,
    safe_enum,
)
from db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20270901_0031_partner_settlements"
down_revision = "20270831_0030_billing_state_machine"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

SETTLEMENT_STATUS = ["DRAFT", "APPROVED", "SENT", "CONFIRMED", "FAILED"]
PAYOUT_ORDER_STATUS = ["QUEUED", "SENT", "CONFIRMED", "FAILED"]


def upgrade():
    bind = op.get_bind()
    ensure_pg_enum(bind, "settlement_status", SETTLEMENT_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "payout_order_status", PAYOUT_ORDER_STATUS, schema=SCHEMA)

    settlement_status_enum = safe_enum(bind, "settlement_status", SETTLEMENT_STATUS, schema=SCHEMA)
    payout_status_enum = safe_enum(bind, "payout_order_status", PAYOUT_ORDER_STATUS, schema=SCHEMA)

    settlement_fk = "settlements.id" if not SCHEMA else f"{SCHEMA}.settlements.id"
    payout_fk = "payout_orders.id" if not SCHEMA else f"{SCHEMA}.payout_orders.id"

    create_table_if_not_exists(
        bind,
        "settlements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("merchant_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("partner_id", sa.String(length=64), nullable=True, index=True),
        sa.Column("period_from", sa.Date, nullable=False, index=True),
        sa.Column("period_to", sa.Date, nullable=False, index=True),
        sa.Column("currency", sa.String(length=8), nullable=False, index=True),
        sa.Column("total_amount", sa.BigInteger, nullable=False),
        sa.Column("commission_amount", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("status", settlement_status_enum, nullable=False, server_default=SETTLEMENT_STATUS[0]),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("merchant_id", "currency", "period_from", "period_to", name="uq_settlement_scope"),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "payout_orders",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("settlement_id", sa.String(length=36), sa.ForeignKey(settlement_fk), nullable=False, index=True),
        sa.Column("partner_bank_details_ref", sa.String(length=255), nullable=True),
        sa.Column("amount", sa.BigInteger, nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("status", payout_status_enum, nullable=False, server_default=PAYOUT_ORDER_STATUS[0], index=True),
        sa.Column("provider_ref", sa.String(length=128), nullable=True, index=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "payout_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("payout_order_id", sa.String(length=36), sa.ForeignKey(payout_fk), nullable=False, index=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )

    if not is_sqlite(bind):
        create_index_if_not_exists(bind, "ix_payout_orders_status", "payout_orders", ["status"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_payout_orders_provider_ref", "payout_orders", ["provider_ref"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_payout_events_order_id", "payout_events", ["payout_order_id"], schema=SCHEMA)


def downgrade():
    bind = op.get_bind()
    drop_table_if_exists(bind, "payout_events", schema=SCHEMA)
    drop_table_if_exists(bind, "payout_orders", schema=SCHEMA)
    drop_table_if_exists(bind, "settlements", schema=SCHEMA)

    # Enums are left in place for safety across deployments
