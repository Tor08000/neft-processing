"""vehicle maintenance v1 tables

Revision ID: 20295100_0113_vehicle_maintenance_v1
Revises: 20295010_0112_vehicle_profile_v1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.utils import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    table_exists,
)
from app.db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20295100_0113_vehicle_maintenance_v1"
down_revision = "20295010_0112_vehicle_profile_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if table_exists(bind, "vehicles", schema=SCHEMA):
        op.add_column("vehicles", sa.Column("generation", sa.String(length=64), nullable=True), schema=SCHEMA)
        op.add_column("vehicles", sa.Column("transmission", sa.String(length=16), nullable=True), schema=SCHEMA)
        op.add_column("vehicles", sa.Column("drive_type", sa.String(length=16), nullable=True), schema=SCHEMA)

    if not table_exists(bind, "maintenance_items", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "maintenance_items",
            schema=SCHEMA,
            columns=(
                sa.Column("code", sa.String(length=64), primary_key=True),
                sa.Column("title", sa.String(length=128), nullable=False),
                sa.Column("description", sa.Text(), nullable=True),
                sa.Column("risk_level", sa.String(length=16), nullable=True),
                sa.Column("default_interval_km", sa.Numeric(), nullable=True),
                sa.Column("default_interval_months", sa.Integer(), nullable=True),
            ),
        )

    if not table_exists(bind, "maintenance_rules", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "maintenance_rules",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("brand", sa.String(length=64), nullable=True),
                sa.Column("model", sa.String(length=64), nullable=True),
                sa.Column("generation", sa.String(length=64), nullable=True),
                sa.Column("year_from", sa.Integer(), nullable=True),
                sa.Column("year_to", sa.Integer(), nullable=True),
                sa.Column("engine_type", sa.String(length=32), nullable=True),
                sa.Column("engine_volume_from", sa.Numeric(), nullable=True),
                sa.Column("engine_volume_to", sa.Numeric(), nullable=True),
                sa.Column("transmission", sa.String(length=16), nullable=True),
                sa.Column("drive_type", sa.String(length=16), nullable=True),
                sa.Column("item_code", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.maintenance_items.code"), nullable=False),
                sa.Column("interval_km", sa.Numeric(), nullable=True),
                sa.Column("interval_months", sa.Integer(), nullable=True),
                sa.Column("conditions", postgresql.JSONB(), nullable=True),
                sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
                sa.Column("source", sa.String(length=32), nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(bind, "ix_maintenance_rules_item", "maintenance_rules", ["item_code"], schema=SCHEMA)

    if not table_exists(bind, "maintenance_modifiers", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "maintenance_modifiers",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("item_code", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.maintenance_items.code"), nullable=False),
                sa.Column("condition_code", sa.String(length=32), nullable=False),
                sa.Column("factor", sa.Numeric(), nullable=False),
            ),
        )
        create_index_if_not_exists(bind, "ix_maintenance_modifiers_item", "maintenance_modifiers", ["item_code"], schema=SCHEMA)

    if not table_exists(bind, "vehicle_usage_profile", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "vehicle_usage_profile",
            schema=SCHEMA,
            columns=(
                sa.Column("vehicle_id", sa.String(length=36), sa.ForeignKey(f"{SCHEMA}.vehicles.id"), primary_key=True),
                sa.Column("usage_type", sa.String(length=16), nullable=True),
                sa.Column("aggressiveness_score", sa.Numeric(), nullable=True),
                sa.Column("heavy_load_flag", sa.Boolean(), nullable=True),
                sa.Column("climate_zone", sa.String(length=16), nullable=True),
                sa.Column("avg_monthly_km", sa.Numeric(), nullable=True),
                sa.Column("avg_consumption_l_100", sa.Numeric(), nullable=True),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )

    if not table_exists(bind, "vehicle_service_records", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "vehicle_service_records",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("vehicle_id", sa.String(length=36), sa.ForeignKey(f"{SCHEMA}.vehicles.id"), nullable=False),
                sa.Column("item_code", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.maintenance_items.code"), nullable=False),
                sa.Column("service_at_km", sa.Numeric(), nullable=True),
                sa.Column("service_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("partner_id", sa.String(length=36), sa.ForeignKey(f"{SCHEMA}.partners.id"), nullable=True),
                sa.Column("order_id", sa.String(length=36), nullable=True),
                sa.Column("note", sa.Text(), nullable=True),
                sa.Column("source", sa.String(length=32), nullable=False),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(bind, "ix_vehicle_service_records_vehicle", "vehicle_service_records", ["vehicle_id"], schema=SCHEMA)

    if not table_exists(bind, "vehicle_maintenance_dismissals", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "vehicle_maintenance_dismissals",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("vehicle_id", sa.String(length=36), sa.ForeignKey(f"{SCHEMA}.vehicles.id"), nullable=False),
                sa.Column("item_code", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.maintenance_items.code"), nullable=False),
                sa.Column("dismissed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(bind, "ix_vehicle_maintenance_dismissals_vehicle", "vehicle_maintenance_dismissals", ["vehicle_id"], schema=SCHEMA)


def downgrade() -> None:
    pass
