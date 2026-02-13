"""add geo fields to stations

Revision ID: 20299620_0171_add_geo_fields_to_stations
Revises: 20299610_0170_logistics_fuel_control_v1
Create Date: 2026-02-12 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, column_exists, index_exists


revision = "20299620_0171_add_geo_fields_to_stations"
down_revision = "20299610_0170_logistics_fuel_control_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if not column_exists(bind, "fuel_stations", "lat", schema=DB_SCHEMA):
        op.add_column("fuel_stations", sa.Column("lat", sa.Float(), nullable=True), schema=DB_SCHEMA)
    else:
        if is_postgres:
            op.execute(f"UPDATE {DB_SCHEMA}.fuel_stations SET lat = NULL WHERE lat !~ '^-?[0-9]+(\.[0-9]+)?$'")
            op.execute(f"ALTER TABLE {DB_SCHEMA}.fuel_stations ALTER COLUMN lat TYPE DOUBLE PRECISION USING lat::double precision")
        else:
            op.alter_column("fuel_stations", "lat", existing_type=sa.String(length=32), type_=sa.Float(), schema=DB_SCHEMA)

    if not column_exists(bind, "fuel_stations", "lon", schema=DB_SCHEMA):
        op.add_column("fuel_stations", sa.Column("lon", sa.Float(), nullable=True), schema=DB_SCHEMA)
    else:
        if is_postgres:
            op.execute(f"UPDATE {DB_SCHEMA}.fuel_stations SET lon = NULL WHERE lon !~ '^-?[0-9]+(\.[0-9]+)?$'")
            op.execute(f"ALTER TABLE {DB_SCHEMA}.fuel_stations ALTER COLUMN lon TYPE DOUBLE PRECISION USING lon::double precision")
        else:
            op.alter_column("fuel_stations", "lon", existing_type=sa.String(length=32), type_=sa.Float(), schema=DB_SCHEMA)

    if not column_exists(bind, "fuel_stations", "nav_url", schema=DB_SCHEMA):
        op.add_column("fuel_stations", sa.Column("nav_url", sa.Text(), nullable=True), schema=DB_SCHEMA)

    if not column_exists(bind, "fuel_stations", "geo_hash", schema=DB_SCHEMA):
        op.add_column("fuel_stations", sa.Column("geo_hash", sa.String(length=16), nullable=True), schema=DB_SCHEMA)

    if not index_exists(bind, "ix_fuel_stations_lat_lon", schema=DB_SCHEMA):
        op.create_index("ix_fuel_stations_lat_lon", "fuel_stations", ["lat", "lon"], unique=False, schema=DB_SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if index_exists(bind, "ix_fuel_stations_lat_lon", schema=DB_SCHEMA):
        op.drop_index("ix_fuel_stations_lat_lon", table_name="fuel_stations", schema=DB_SCHEMA)

    if column_exists(bind, "fuel_stations", "geo_hash", schema=DB_SCHEMA):
        op.drop_column("fuel_stations", "geo_hash", schema=DB_SCHEMA)

    if column_exists(bind, "fuel_stations", "nav_url", schema=DB_SCHEMA):
        op.drop_column("fuel_stations", "nav_url", schema=DB_SCHEMA)

    if column_exists(bind, "fuel_stations", "lon", schema=DB_SCHEMA):
        if is_postgres:
            op.execute(f"ALTER TABLE {DB_SCHEMA}.fuel_stations ALTER COLUMN lon TYPE VARCHAR(32) USING lon::varchar")
        else:
            op.alter_column("fuel_stations", "lon", existing_type=sa.Float(), type_=sa.String(length=32), schema=DB_SCHEMA)

    if column_exists(bind, "fuel_stations", "lat", schema=DB_SCHEMA):
        if is_postgres:
            op.execute(f"ALTER TABLE {DB_SCHEMA}.fuel_stations ALTER COLUMN lat TYPE VARCHAR(32) USING lat::varchar")
        else:
            op.alter_column("fuel_stations", "lat", existing_type=sa.Float(), type_=sa.String(length=32), schema=DB_SCHEMA)
