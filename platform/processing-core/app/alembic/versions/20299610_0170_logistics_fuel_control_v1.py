"""logistics fuel control v1

Revision ID: 20299610_0170_logistics_fuel_control_v1
Revises: 20299400_0167_marketplace_client_events_v1
Create Date: 2026-02-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from app.db.types import GUID

# revision identifiers, used by Alembic.
revision = "20299610_0170_logistics_fuel_control_v1"
down_revision = "20299400_0167_marketplace_client_events_v1"
branch_labels = None
depends_on = None

SCHEMA = "processing_core"


def upgrade() -> None:
    bind = op.get_bind()

    pg.ENUM(
        "TIME_WINDOW_MATCH",
        "ROUTE_PROXIMITY_MATCH",
        "STATION_ON_ROUTE",
        "MANUAL_LINK",
        name="logistics_fuel_link_reason",
        schema=SCHEMA,
    ).create(bind, checkfirst=True)

    pg.ENUM(
        "SYSTEM",
        "USER",
        name="logistics_fuel_linked_by",
        schema=SCHEMA,
    ).create(bind, checkfirst=True)

    pg.ENUM(
        "OUT_OF_TIME_WINDOW",
        "OUT_OF_ROUTE",
        "HIGH_CONSUMPTION",
        name="logistics_fuel_alert_type",
        schema=SCHEMA,
    ).create(bind, checkfirst=True)

    pg.ENUM(
        "INFO",
        "WARN",
        "CRITICAL",
        name="logistics_fuel_alert_severity",
        schema=SCHEMA,
    ).create(bind, checkfirst=True)

    pg.ENUM(
        "OPEN",
        "ACKED",
        "CLOSED",
        name="logistics_fuel_alert_status",
        schema=SCHEMA,
    ).create(bind, checkfirst=True)

    link_reason = pg.ENUM(
        "TIME_WINDOW_MATCH",
        "ROUTE_PROXIMITY_MATCH",
        "STATION_ON_ROUTE",
        "MANUAL_LINK",
        name="logistics_fuel_link_reason",
        schema=SCHEMA,
        create_type=False,
    )
    linked_by = pg.ENUM(
        "SYSTEM",
        "USER",
        name="logistics_fuel_linked_by",
        schema=SCHEMA,
        create_type=False,
    )
    alert_type = pg.ENUM(
        "OUT_OF_TIME_WINDOW",
        "OUT_OF_ROUTE",
        "HIGH_CONSUMPTION",
        name="logistics_fuel_alert_type",
        schema=SCHEMA,
        create_type=False,
    )
    alert_severity = pg.ENUM(
        "INFO",
        "WARN",
        "CRITICAL",
        name="logistics_fuel_alert_severity",
        schema=SCHEMA,
        create_type=False,
    )
    alert_status = pg.ENUM(
        "OPEN",
        "ACKED",
        "CLOSED",
        name="logistics_fuel_alert_status",
        schema=SCHEMA,
        create_type=False,
    )

    op.create_table(
        "logistics_fuel_links",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("trip_id", GUID(), nullable=False),
        sa.Column("fuel_tx_id", GUID(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("reason", link_reason, nullable=False),
        sa.Column("linked_by", linked_by, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["fuel_tx_id"], [f"{SCHEMA}.fuel_transactions.id"]),
        sa.ForeignKeyConstraint(["trip_id"], [f"{SCHEMA}.logistics_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fuel_tx_id", name="uq_logistics_fuel_links_fuel_tx_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_logistics_fuel_links_trip_id", "logistics_fuel_links", ["trip_id"], unique=False, schema=SCHEMA)
    op.create_index(
        "ix_logistics_fuel_links_client_created",
        "logistics_fuel_links",
        ["client_id", "created_at"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "logistics_fuel_alerts",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("trip_id", GUID(), nullable=True),
        sa.Column("fuel_tx_id", GUID(), nullable=False),
        sa.Column("type", alert_type, nullable=False),
        sa.Column("severity", alert_severity, nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("details", sa.String(length=1024), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("status", alert_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["fuel_tx_id"], [f"{SCHEMA}.fuel_transactions.id"]),
        sa.ForeignKeyConstraint(["trip_id"], [f"{SCHEMA}.logistics_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_logistics_fuel_alerts_client_created",
        "logistics_fuel_alerts",
        ["client_id", "created_at"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index("ix_logistics_fuel_alerts_trip_id", "logistics_fuel_alerts", ["trip_id"], unique=False, schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_logistics_fuel_alerts_trip_id", table_name="logistics_fuel_alerts", schema=SCHEMA)
    op.drop_index("ix_logistics_fuel_alerts_client_created", table_name="logistics_fuel_alerts", schema=SCHEMA)
    op.drop_table("logistics_fuel_alerts", schema=SCHEMA)
    op.drop_index("ix_logistics_fuel_links_client_created", table_name="logistics_fuel_links", schema=SCHEMA)
    op.drop_index("ix_logistics_fuel_links_trip_id", table_name="logistics_fuel_links", schema=SCHEMA)
    op.drop_table("logistics_fuel_links", schema=SCHEMA)

    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.logistics_fuel_alert_status")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.logistics_fuel_alert_severity")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.logistics_fuel_alert_type")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.logistics_fuel_linked_by")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.logistics_fuel_link_reason")
