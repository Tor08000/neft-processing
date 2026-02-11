"""logistics fuel control v1

Revision ID: 20299610_0170_logistics_fuel_control_v1
Revises: 20299400_0167_marketplace_client_events_v1
Create Date: 2026-02-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from app.db.types import ExistingEnum, GUID
from app.models.logistics import (
    LogisticsFuelAlertSeverity,
    LogisticsFuelAlertStatus,
    LogisticsFuelAlertType,
    LogisticsFuelLinkedBy,
    LogisticsFuelLinkReason,
)

# revision identifiers, used by Alembic.
revision = "20299610_0170_logistics_fuel_control_v1"
down_revision = "20299400_0167_marketplace_client_events_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "logistics_fuel_links",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("trip_id", GUID(), nullable=False),
        sa.Column("fuel_tx_id", GUID(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("reason", ExistingEnum(LogisticsFuelLinkReason, name="logistics_fuel_link_reason"), nullable=False),
        sa.Column("linked_by", ExistingEnum(LogisticsFuelLinkedBy, name="logistics_fuel_linked_by"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["fuel_tx_id"], ["fuel_transactions.id"]),
        sa.ForeignKeyConstraint(["trip_id"], ["logistics_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fuel_tx_id", name="uq_logistics_fuel_links_fuel_tx_id"),
    )
    op.create_index("ix_logistics_fuel_links_trip_id", "logistics_fuel_links", ["trip_id"], unique=False)
    op.create_index("ix_logistics_fuel_links_client_created", "logistics_fuel_links", ["client_id", "created_at"], unique=False)

    op.create_table(
        "logistics_fuel_alerts",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("trip_id", GUID(), nullable=True),
        sa.Column("fuel_tx_id", GUID(), nullable=False),
        sa.Column("type", ExistingEnum(LogisticsFuelAlertType, name="logistics_fuel_alert_type"), nullable=False),
        sa.Column("severity", ExistingEnum(LogisticsFuelAlertSeverity, name="logistics_fuel_alert_severity"), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("details", sa.String(length=1024), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("status", ExistingEnum(LogisticsFuelAlertStatus, name="logistics_fuel_alert_status"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["fuel_tx_id"], ["fuel_transactions.id"]),
        sa.ForeignKeyConstraint(["trip_id"], ["logistics_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_logistics_fuel_alerts_client_created", "logistics_fuel_alerts", ["client_id", "created_at"], unique=False)
    op.create_index("ix_logistics_fuel_alerts_trip_id", "logistics_fuel_alerts", ["trip_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_logistics_fuel_alerts_trip_id", table_name="logistics_fuel_alerts")
    op.drop_index("ix_logistics_fuel_alerts_client_created", table_name="logistics_fuel_alerts")
    op.drop_table("logistics_fuel_alerts")
    op.drop_index("ix_logistics_fuel_links_client_created", table_name="logistics_fuel_links")
    op.drop_index("ix_logistics_fuel_links_trip_id", table_name="logistics_fuel_links")
    op.drop_table("logistics_fuel_links")
