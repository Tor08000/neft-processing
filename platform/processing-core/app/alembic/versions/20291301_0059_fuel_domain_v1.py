"""fuel domain v1 tables and enums

Revision ID: 20291301_0059_fuel_domain_v1
Revises: 20291220_0058_legal_graph_enum_updates
Create Date: 2029-01-30 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import ensure_pg_enum, ensure_pg_enum_value, table_exists
from app.db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

# revision identifiers, used by Alembic.
revision = "20291301_0059_fuel_domain_v1"
down_revision = "20291220_0058_legal_graph_enum_updates"
branch_labels = None
depends_on = None


FUEL_CARD_STATUS = ["ACTIVE", "BLOCKED", "LOST", "EXPIRED"]
FUEL_STATION_STATUS = ["ACTIVE", "INACTIVE"]
FUEL_NETWORK_STATUS = ["ACTIVE", "INACTIVE"]
FUEL_TX_STATUS = ["AUTHORIZED", "REVIEW_REQUIRED", "DECLINED", "REVERSED", "SETTLED"]
FUEL_LIMIT_SCOPE_TYPE = ["CLIENT", "CARD", "CARD_GROUP", "VEHICLE", "DRIVER"]
FUEL_LIMIT_TYPE = ["AMOUNT", "VOLUME", "COUNT"]
FUEL_LIMIT_PERIOD = ["DAILY", "WEEKLY", "MONTHLY"]
FUEL_TYPE = ["DIESEL", "AI-92", "AI-95", "AI-98", "GAS", "OTHER"]
FLEET_VEHICLE_STATUS = ["ACTIVE", "INACTIVE"]
FLEET_DRIVER_STATUS = ["ACTIVE", "INACTIVE"]
FUEL_CARD_GROUP_STATUS = ["ACTIVE", "INACTIVE"]

FUEL_CARD_STATUS_ENUM = postgresql.ENUM(
    *FUEL_CARD_STATUS,
    name="fuel_card_status",
    schema=SCHEMA,
    create_type=False,
)
FUEL_STATION_STATUS_ENUM = postgresql.ENUM(
    *FUEL_STATION_STATUS,
    name="fuel_station_status",
    schema=SCHEMA,
    create_type=False,
)
FUEL_NETWORK_STATUS_ENUM = postgresql.ENUM(
    *FUEL_NETWORK_STATUS,
    name="fuel_network_status",
    schema=SCHEMA,
    create_type=False,
)
FUEL_TX_STATUS_ENUM = postgresql.ENUM(
    *FUEL_TX_STATUS,
    name="fuel_tx_status",
    schema=SCHEMA,
    create_type=False,
)
FUEL_LIMIT_SCOPE_TYPE_ENUM = postgresql.ENUM(
    *FUEL_LIMIT_SCOPE_TYPE,
    name="fuel_limit_scope_type",
    schema=SCHEMA,
    create_type=False,
)
FUEL_LIMIT_TYPE_ENUM = postgresql.ENUM(
    *FUEL_LIMIT_TYPE,
    name="fuel_limit_type",
    schema=SCHEMA,
    create_type=False,
)
FUEL_LIMIT_PERIOD_ENUM = postgresql.ENUM(
    *FUEL_LIMIT_PERIOD,
    name="fuel_limit_period",
    schema=SCHEMA,
    create_type=False,
)
FUEL_TYPE_ENUM = postgresql.ENUM(
    *FUEL_TYPE,
    name="fuel_type",
    schema=SCHEMA,
    create_type=False,
)
FLEET_VEHICLE_STATUS_ENUM = postgresql.ENUM(
    *FLEET_VEHICLE_STATUS,
    name="fleet_vehicle_status",
    schema=SCHEMA,
    create_type=False,
)
FLEET_DRIVER_STATUS_ENUM = postgresql.ENUM(
    *FLEET_DRIVER_STATUS,
    name="fleet_driver_status",
    schema=SCHEMA,
    create_type=False,
)
FUEL_CARD_GROUP_STATUS_ENUM = postgresql.ENUM(
    *FUEL_CARD_GROUP_STATUS,
    name="fuel_card_group_status",
    schema=SCHEMA,
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "fuel_card_status", FUEL_CARD_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "fuel_station_status", FUEL_STATION_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "fuel_network_status", FUEL_NETWORK_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "fuel_tx_status", FUEL_TX_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "fuel_limit_scope_type", FUEL_LIMIT_SCOPE_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "fuel_limit_type", FUEL_LIMIT_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "fuel_limit_period", FUEL_LIMIT_PERIOD, schema=SCHEMA)
    ensure_pg_enum(bind, "fuel_type", FUEL_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "fleet_vehicle_status", FLEET_VEHICLE_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "fleet_driver_status", FLEET_DRIVER_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "fuel_card_group_status", FUEL_CARD_GROUP_STATUS, schema=SCHEMA)

    ensure_pg_enum_value(bind, "internal_ledger_transaction_type", "FUEL_SETTLEMENT", schema=SCHEMA)
    ensure_pg_enum_value(bind, "internal_ledger_transaction_type", "FUEL_REVERSAL", schema=SCHEMA)
    ensure_pg_enum_value(bind, "legal_node_type", "FUEL_TRANSACTION", schema=SCHEMA)
    ensure_pg_enum_value(bind, "legal_node_type", "CARD", schema=SCHEMA)
    ensure_pg_enum_value(bind, "legal_node_type", "FUEL_STATION", schema=SCHEMA)
    ensure_pg_enum_value(bind, "legal_node_type", "VEHICLE", schema=SCHEMA)
    ensure_pg_enum_value(bind, "risksubjecttype", "FUEL_TRANSACTION", schema=SCHEMA)

    if not table_exists(bind, "fleet_vehicles", schema=SCHEMA):
        op.create_table(
            "fleet_vehicles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False),
            sa.Column("client_id", sa.String(64), nullable=False),
            sa.Column("plate_number", sa.String(32), nullable=False),
            sa.Column("vin", sa.String(64), nullable=True),
            sa.Column("brand", sa.String(64), nullable=True),
            sa.Column("model", sa.String(64), nullable=True),
            sa.Column("fuel_type_preferred", sa.String(32), nullable=True),
            sa.Column("tank_capacity_liters", sa.BigInteger, nullable=True),
            sa.Column(
                "status",
                FLEET_VEHICLE_STATUS_ENUM,
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("client_id", "plate_number", name="uq_fleet_vehicle_plate_client"),
            schema=SCHEMA,
        )
        op.create_index("ix_fleet_vehicles_client_id", "fleet_vehicles", ["client_id"], schema=SCHEMA)
        op.create_index("ix_fleet_vehicles_tenant_id", "fleet_vehicles", ["tenant_id"], schema=SCHEMA)

    if not table_exists(bind, "fleet_drivers", schema=SCHEMA):
        op.create_table(
            "fleet_drivers",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False),
            sa.Column("client_id", sa.String(64), nullable=False),
            sa.Column("full_name", sa.String(128), nullable=False),
            sa.Column("phone", sa.String(32), nullable=True),
            sa.Column(
                "status",
                FLEET_DRIVER_STATUS_ENUM,
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index("ix_fleet_drivers_client_id", "fleet_drivers", ["client_id"], schema=SCHEMA)
        op.create_index("ix_fleet_drivers_tenant_id", "fleet_drivers", ["tenant_id"], schema=SCHEMA)

    if not table_exists(bind, "fuel_card_groups", schema=SCHEMA):
        op.create_table(
            "fuel_card_groups",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False),
            sa.Column("client_id", sa.String(64), nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column(
                "status",
                FUEL_CARD_GROUP_STATUS_ENUM,
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index("ix_fuel_card_groups_client_id", "fuel_card_groups", ["client_id"], schema=SCHEMA)
        op.create_index("ix_fuel_card_groups_tenant_id", "fuel_card_groups", ["tenant_id"], schema=SCHEMA)

    if not table_exists(bind, "fuel_cards", schema=SCHEMA):
        op.create_table(
            "fuel_cards",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False),
            sa.Column("client_id", sa.String(64), nullable=False),
            sa.Column("card_token", sa.String(128), nullable=False),
            sa.Column("status", FUEL_CARD_STATUS_ENUM, nullable=False),
            sa.Column("card_group_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fuel_card_groups.id"), nullable=True),
            sa.Column("vehicle_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fleet_vehicles.id"), nullable=True),
            sa.Column("driver_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fleet_drivers.id"), nullable=True),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("meta", sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "card_token", name="uq_fuel_cards_tenant_token"),
            schema=SCHEMA,
        )
        op.create_index("ix_fuel_cards_card_token", "fuel_cards", ["card_token"], schema=SCHEMA)
        op.create_index("ix_fuel_cards_client_id", "fuel_cards", ["client_id"], schema=SCHEMA)
        op.create_index("ix_fuel_cards_tenant_id", "fuel_cards", ["tenant_id"], schema=SCHEMA)

    if not table_exists(bind, "fuel_networks", schema=SCHEMA):
        op.create_table(
            "fuel_networks",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("provider_code", sa.String(64), nullable=False),
            sa.Column("status", FUEL_NETWORK_STATUS_ENUM, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index("ix_fuel_networks_provider_code", "fuel_networks", ["provider_code"], schema=SCHEMA, unique=True)

    if not table_exists(bind, "fuel_stations", schema=SCHEMA):
        op.create_table(
            "fuel_stations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("network_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fuel_networks.id"), nullable=False),
            sa.Column("name", sa.String(256), nullable=False),
            sa.Column("country", sa.String(64), nullable=True),
            sa.Column("region", sa.String(64), nullable=True),
            sa.Column("city", sa.String(64), nullable=True),
            sa.Column("lat", sa.String(32), nullable=True),
            sa.Column("lon", sa.String(32), nullable=True),
            sa.Column("mcc", sa.String(8), nullable=True),
            sa.Column("station_code", sa.String(64), nullable=True),
            sa.Column("status", FUEL_STATION_STATUS_ENUM, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("network_id", "station_code", name="uq_fuel_station_code_network"),
            schema=SCHEMA,
        )
        op.create_index("ix_fuel_stations_network_id", "fuel_stations", ["network_id"], schema=SCHEMA)
        op.create_index("ix_fuel_stations_station_code", "fuel_stations", ["station_code"], schema=SCHEMA)

    if not table_exists(bind, "fuel_transactions", schema=SCHEMA):
        op.create_table(
            "fuel_transactions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False),
            sa.Column("client_id", sa.String(64), nullable=False),
            sa.Column("card_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fuel_cards.id"), nullable=False),
            sa.Column("vehicle_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fleet_vehicles.id"), nullable=True),
            sa.Column("driver_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fleet_drivers.id"), nullable=True),
            sa.Column("station_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fuel_stations.id"), nullable=False),
            sa.Column("network_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fuel_networks.id"), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("fuel_type", FUEL_TYPE_ENUM, nullable=False),
            sa.Column("volume_ml", sa.BigInteger, nullable=False),
            sa.Column("unit_price_minor", sa.BigInteger, nullable=False),
            sa.Column("amount_total_minor", sa.BigInteger, nullable=False),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("status", FUEL_TX_STATUS_ENUM, nullable=False),
            sa.Column("decline_code", sa.String(64), nullable=True),
            sa.Column(
                "risk_decision_id",
                sa.String(36),
                sa.ForeignKey(f"{SCHEMA}.risk_decisions.id"),
                nullable=True,
            ),
            sa.Column(
                "ledger_transaction_id",
                sa.String(36),
                sa.ForeignKey(f"{SCHEMA}.internal_ledger_transactions.id"),
                nullable=True,
            ),
            sa.Column("external_ref", sa.String(128), nullable=True),
            sa.Column("meta", sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_fuel_transactions_client_time",
            "fuel_transactions",
            ["client_id", "occurred_at"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_fuel_transactions_card_time",
            "fuel_transactions",
            ["card_id", "occurred_at"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_fuel_transactions_vehicle_time",
            "fuel_transactions",
            ["vehicle_id", "occurred_at"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_fuel_transactions_status_time",
            "fuel_transactions",
            ["status", "occurred_at"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_fuel_transactions_external_ref",
            "fuel_transactions",
            ["external_ref"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "fuel_limits", schema=SCHEMA):
        op.create_table(
            "fuel_limits",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False),
            sa.Column("client_id", sa.String(64), nullable=False),
            sa.Column(
                "scope_type",
                FUEL_LIMIT_SCOPE_TYPE_ENUM,
                nullable=False,
            ),
            sa.Column("scope_id", sa.String(64), nullable=True),
            sa.Column(
                "limit_type",
                FUEL_LIMIT_TYPE_ENUM,
                nullable=False,
            ),
            sa.Column(
                "period",
                FUEL_LIMIT_PERIOD_ENUM,
                nullable=False,
            ),
            sa.Column("value", sa.BigInteger, nullable=False),
            sa.Column("currency", sa.String(3), nullable=True),
            sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
            sa.Column("meta", sa.JSON, nullable=True),
            sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_fuel_limits_scope_active",
            "fuel_limits",
            ["tenant_id", "client_id", "scope_type", "scope_id", "active"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_fuel_limits_validity",
            "fuel_limits",
            ["valid_from", "valid_to"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    # Tables and enum values are left in place to preserve history.
    pass
