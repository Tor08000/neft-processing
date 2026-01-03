"""fuel provider integrations v1.

Revision ID: 20291980_0106_fuel_provider_integrations_v1
Revises: 20291970_0105_fleet_telegram_notifications_v1
Create Date: 2026-01-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import (
    DB_SCHEMA,
    column_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)


# revision identifiers, used by Alembic.
revision = "20291980_0106_fuel_provider_integrations_v1"
down_revision = "20291970_0105_fleet_telegram_notifications_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(
        bind,
        "fuel_provider_connection_status",
        ["ACTIVE", "DISABLED", "ERROR"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "fuel_provider_auth_type",
        ["API_KEY", "OAUTH2", "EDI"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "fuel_ingest_mode",
        ["POLL", "BACKFILL", "REPLAY", "EDI"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "fuel_provider_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("provider_code", sa.String(64), nullable=False),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "fuel_provider_connection_status",
                ["ACTIVE", "DISABLED", "ERROR"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column(
            "auth_type",
            safe_enum(
                bind,
                "fuel_provider_auth_type",
                ["API_KEY", "OAUTH2", "EDI"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("secret_ref", sa.String(256), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_cursor", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("audit_event_id", sa.String(36), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "uq_fuel_provider_conn_client_provider",
        "fuel_provider_connections",
        ["client_id", "provider_code"],
        unique=True,
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_fuel_provider_conn_status",
        "fuel_provider_connections",
        ["status"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "fuel_provider_card_map",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("provider_code", sa.String(64), nullable=False),
        sa.Column("card_id", sa.String(36), nullable=False),
        sa.Column("provider_card_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "uq_fuel_provider_card_id",
        "fuel_provider_card_map",
        ["provider_code", "provider_card_id"],
        unique=True,
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "uq_fuel_provider_card_card",
        "fuel_provider_card_map",
        ["provider_code", "card_id"],
        unique=True,
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_fuel_provider_card_client",
        "fuel_provider_card_map",
        ["client_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "fuel_provider_raw_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("provider_code", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("provider_event_id", sa.String(128), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_redacted", sa.JSON(), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("ingest_job_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_fuel_provider_raw_events_client_created",
        "fuel_provider_raw_events",
        ["client_id", "created_at"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_fuel_provider_raw_events_provider_created",
        "fuel_provider_raw_events",
        ["provider_code", "created_at"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "uq_fuel_provider_raw_event_provider_event",
        "fuel_provider_raw_events",
        ["provider_code", "provider_event_id"],
        unique=True,
        schema=DB_SCHEMA,
        postgresql_where=sa.text("provider_event_id IS NOT NULL"),
    )

    if not column_exists(bind, "fuel_ingest_jobs", "mode", schema=DB_SCHEMA):
        op.add_column(
            "fuel_ingest_jobs",
            sa.Column(
                "mode",
                safe_enum(
                    bind,
                    "fuel_ingest_mode",
                    ["POLL", "BACKFILL", "REPLAY", "EDI"],
                    schema=DB_SCHEMA,
                ),
                nullable=True,
            ),
            schema=DB_SCHEMA,
        )
    if not column_exists(bind, "fuel_ingest_jobs", "cursor", schema=DB_SCHEMA):
        op.add_column("fuel_ingest_jobs", sa.Column("cursor", sa.String(256), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "fuel_ingest_jobs", "window_start", schema=DB_SCHEMA):
        op.add_column(
            "fuel_ingest_jobs",
            sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
            schema=DB_SCHEMA,
        )
    if not column_exists(bind, "fuel_ingest_jobs", "window_end", schema=DB_SCHEMA):
        op.add_column(
            "fuel_ingest_jobs",
            sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
            schema=DB_SCHEMA,
        )


def downgrade() -> None:
    # No downgrade operations for additive changes.
    pass
