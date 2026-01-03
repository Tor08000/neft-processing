"""Service bookings v1.

Revision ID: 20296000_0113_service_bookings_v1
Revises: 20295010_0112_vehicle_profile_v1
Create Date: 2026-03-01 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from app.alembic.helpers import (
    DB_SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    ensure_pg_enum_value,
    is_postgres,
    safe_enum,
)
from app.db.types import GUID


revision = "20296000_0113_service_bookings_v1"
down_revision = "20295010_0112_vehicle_profile_v1"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def _schema_prefix() -> str:
    return f"{DB_SCHEMA}." if DB_SCHEMA else ""


def _create_worm_guard(table_name: str) -> None:
    if not is_postgres(op.get_bind()):
        return
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {_schema_prefix()}{table_name}_worm_guard()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION '{table_name} is WORM';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            DROP TRIGGER IF EXISTS {table_name}_worm_update
            ON {_schema_prefix()}{table_name}
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {table_name}_worm_update
            BEFORE UPDATE ON {_schema_prefix()}{table_name}
            FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}{table_name}_worm_guard()
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            DROP TRIGGER IF EXISTS {table_name}_worm_delete
            ON {_schema_prefix()}{table_name}
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {table_name}_worm_delete
            BEFORE DELETE ON {_schema_prefix()}{table_name}
            FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}{table_name}_worm_guard()
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "partner_service_status", ["ACTIVE", "PAUSED"], schema=DB_SCHEMA)
    ensure_pg_enum(bind, "partner_resource_type", ["BAY", "TECHNICIAN"], schema=DB_SCHEMA)
    ensure_pg_enum(bind, "partner_resource_status", ["ACTIVE", "INACTIVE"], schema=DB_SCHEMA)
    ensure_pg_enum(
        bind,
        "service_booking_status",
        ["REQUESTED", "CONFIRMED", "DECLINED", "CANCELED", "IN_PROGRESS", "COMPLETED", "NO_SHOW"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(bind, "booking_payment_status", ["NONE", "AUTHORIZED", "PAID", "REFUNDED"], schema=DB_SCHEMA)
    ensure_pg_enum(
        bind,
        "service_booking_event_type",
        [
            "CREATED",
            "SLOT_LOCKED",
            "CONFIRMED",
            "DECLINED",
            "CANCELED",
            "RESCHEDULED",
            "PAID",
            "REFUNDED",
            "STARTED",
            "COMPLETED",
            "NO_SHOW",
        ],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "service_booking_actor_type",
        ["CLIENT", "PARTNER", "SYSTEM", "ADMIN"],
        schema=DB_SCHEMA,
    )

    for value in (
        "BOOKING_CREATED",
        "SLOT_LOCKED",
        "BOOKING_CONFIRMED",
        "BOOKING_DECLINED",
        "BOOKING_CANCELED",
        "BOOKING_STATUS_CHANGED",
        "BOOKING_COMPLETED",
        "SERVICE_RECORD_CREATED",
    ):
        ensure_pg_enum_value(bind, "case_event_type", value, schema=DB_SCHEMA)

    ensure_pg_enum_value(bind, "case_kind", "booking", schema=DB_SCHEMA)

    create_table_if_not_exists(
        bind,
        "partner_services",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_code", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("base_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False, server_default="RUB"),
        sa.Column("requires_vehicle", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("requires_odometer", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "status",
            safe_enum(bind, "partner_service_status", ["ACTIVE", "PAUSED"], schema=DB_SCHEMA),
            nullable=False,
        ),
        sa.Column("meta", JSON_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_partner_services_partner_status",
        "partner_services",
        ["partner_id", "status"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_service_calendars",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("location_id", GUID(), nullable=True),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("working_hours", JSON_TYPE, nullable=False),
        sa.Column("holidays", JSON_TYPE, nullable=True),
        sa.Column("slot_step_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_partner_service_calendars_partner",
        "partner_service_calendars",
        ["partner_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_resources",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "resource_type",
            safe_enum(bind, "partner_resource_type", ["BAY", "TECHNICIAN"], schema=DB_SCHEMA),
            nullable=False,
        ),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "status",
            safe_enum(bind, "partner_resource_status", ["ACTIVE", "INACTIVE"], schema=DB_SCHEMA),
            nullable=False,
        ),
        sa.Column("meta", JSON_TYPE, nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_partner_resources_partner_status",
        "partner_resources",
        ["partner_id", "status"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "service_availability_rules",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("service_id", GUID(), nullable=False),
        sa.Column("resource_ids", postgresql.ARRAY(GUID()), nullable=True),
        sa.Column("lead_time_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("max_days_ahead", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("parallel_capacity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("meta", JSON_TYPE, nullable=True),
        sa.ForeignKeyConstraint(
            ["service_id"],
            [f"{_schema_prefix()}partner_services.id"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_service_availability_rules_service",
        "service_availability_rules",
        ["service_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "service_bookings",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("booking_number", sa.Text(), nullable=False),
        sa.Column("client_id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=True),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("service_id", GUID(), nullable=False),
        sa.Column("vehicle_id", GUID(), nullable=True),
        sa.Column("odometer_km", sa.Numeric(18, 4), nullable=True),
        sa.Column("recommendation_id", GUID(), nullable=True),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "service_booking_status",
                ["REQUESTED", "CONFIRMED", "DECLINED", "CANCELED", "IN_PROGRESS", "COMPLETED", "NO_SHOW"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resource_id", GUID(), nullable=True),
        sa.Column("price_snapshot_json", JSON_TYPE, nullable=False),
        sa.Column("promo_applied_json", JSON_TYPE, nullable=True),
        sa.Column(
            "payment_status",
            safe_enum(bind, "booking_payment_status", ["NONE", "AUTHORIZED", "PAID", "REFUNDED"], schema=DB_SCHEMA),
            nullable=False,
        ),
        sa.Column("client_note", sa.Text(), nullable=True),
        sa.Column("partner_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["service_id"],
            [f"{_schema_prefix()}partner_services.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            [f"{_schema_prefix()}vehicles.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            [f"{_schema_prefix()}vehicle_recommendations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            [f"{_schema_prefix()}partner_resources.id"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "ux_service_bookings_number",
        "service_bookings",
        ["booking_number"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_service_bookings_client_created",
        "service_bookings",
        ["client_id", "created_at"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_service_bookings_partner_created",
        "service_bookings",
        ["partner_id", "created_at"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_service_bookings_status_start",
        "service_bookings",
        ["status", "starts_at"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "booking_slot_locks",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("service_id", GUID(), nullable=False),
        sa.Column("resource_id", GUID(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_id", GUID(), nullable=False),
        sa.Column("booking_id", GUID(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["service_id"],
            [f"{_schema_prefix()}partner_services.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            [f"{_schema_prefix()}partner_resources.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            [f"{_schema_prefix()}service_bookings.id"],
            ondelete="SET NULL",
        ),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_booking_slot_locks_partner_start",
        "booking_slot_locks",
        ["partner_id", "starts_at"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_booking_slot_locks_expires",
        "booking_slot_locks",
        ["expires_at"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "service_booking_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("booking_id", GUID(), nullable=False),
        sa.Column(
            "event_type",
            safe_enum(
                bind,
                "service_booking_event_type",
                [
                    "CREATED",
                    "SLOT_LOCKED",
                    "CONFIRMED",
                    "DECLINED",
                    "CANCELED",
                    "RESCHEDULED",
                    "PAID",
                    "REFUNDED",
                    "STARTED",
                    "COMPLETED",
                    "NO_SHOW",
                ],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column(
            "actor_type",
            safe_enum(bind, "service_booking_actor_type", ["CLIENT", "PARTNER", "SYSTEM", "ADMIN"], schema=DB_SCHEMA),
            nullable=False,
        ),
        sa.Column("actor_id", GUID(), nullable=True),
        sa.Column("payload", JSON_TYPE, nullable=False),
        sa.Column("audit_event_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            [f"{_schema_prefix()}service_bookings.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["audit_event_id"],
            [f"{_schema_prefix()}case_events.id"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_service_booking_events_booking_created",
        "service_booking_events",
        ["booking_id", "created_at"],
        schema=DB_SCHEMA,
    )
    _create_worm_guard("service_booking_events")

    create_table_if_not_exists(
        bind,
        "vehicle_service_records",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", GUID(), nullable=False),
        sa.Column("booking_id", GUID(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column(
            "service_type",
            safe_enum(
                bind,
                "vehicle_service_type",
                ["OIL_CHANGE", "FILTERS", "BRAKES", "TIMING", "OTHER"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("service_at_km", sa.Numeric(18, 4), nullable=False),
        sa.Column("service_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            [f"{_schema_prefix()}vehicles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            [f"{_schema_prefix()}service_bookings.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["partner_id"],
            [f"{_schema_prefix()}partners.id"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_vehicle_service_records_vehicle",
        "vehicle_service_records",
        ["vehicle_id", "service_at"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("vehicle_service_records", schema=DB_SCHEMA)
    op.drop_table("service_booking_events", schema=DB_SCHEMA)
    op.drop_table("booking_slot_locks", schema=DB_SCHEMA)
    op.drop_table("service_bookings", schema=DB_SCHEMA)
    op.drop_table("service_availability_rules", schema=DB_SCHEMA)
    op.drop_table("partner_resources", schema=DB_SCHEMA)
    op.drop_table("partner_service_calendars", schema=DB_SCHEMA)
    op.drop_table("partner_services", schema=DB_SCHEMA)
