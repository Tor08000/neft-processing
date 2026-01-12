"""fleet ingestion v1

Revision ID: 20260201_0104_fleet_ingestion_v1
Revises: 20250220_0103_fuel_fleet_v1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import (
    column_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    ensure_pg_enum_value,
    table_exists,
)
from db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20260201_0104_fleet_ingestion_v1"
down_revision = "20250220_0103_fuel_fleet_v1"
branch_labels = None
depends_on = None

FUEL_PROVIDER_STATUS = ["ACTIVE", "DISABLED"]
FUEL_INGEST_JOB_STATUS = ["RECEIVED", "PROCESSED", "FAILED"]
FUEL_LIMIT_CHECK_STATUS = ["OK", "SOFT_BREACH", "HARD_BREACH"]
FUEL_LIMIT_BREACH_STATUS = ["OPEN", "ACKED", "IGNORED"]
FUEL_LIMIT_BREACH_TYPE = ["AMOUNT", "VOLUME", "CATEGORY", "STATION"]
FUEL_LIMIT_BREACH_SCOPE_TYPE = ["card", "group"]

CASE_EVENT_TYPES = [
    "FLEET_TRANSACTIONS_INGESTED",
    "FLEET_INGEST_FAILED",
    "FUEL_LIMIT_BREACH_DETECTED",
    "FLEET_ALERT_STATUS_UPDATED",
]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "fuel_provider_status", FUEL_PROVIDER_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "fuel_ingest_job_status", FUEL_INGEST_JOB_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "fuel_limit_check_status", FUEL_LIMIT_CHECK_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "fuel_limit_breach_status", FUEL_LIMIT_BREACH_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "fuel_limit_breach_type", FUEL_LIMIT_BREACH_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "fuel_limit_breach_scope_type", FUEL_LIMIT_BREACH_SCOPE_TYPE, schema=SCHEMA)
    for value in CASE_EVENT_TYPES:
        ensure_pg_enum_value(bind, "case_event_type", value, schema=SCHEMA)

    if not table_exists(bind, "fuel_providers", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fuel_providers",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("code", sa.String(length=64), nullable=False),
                sa.Column("name", sa.String(length=128), nullable=False),
                sa.Column(
                    "status",
                    sa.Enum(*FUEL_PROVIDER_STATUS, name="fuel_provider_status", native_enum=False),
                    nullable=False,
                ),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_unique_index_if_not_exists(bind, "uq_fuel_providers_code", "fuel_providers", ["code"], schema=SCHEMA)

    if not table_exists(bind, "fuel_merchants", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fuel_merchants",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("provider_code", sa.String(length=64), nullable=False),
                sa.Column("merchant_key", sa.String(length=256), nullable=False),
                sa.Column("display_name", sa.String(length=256), nullable=False),
                sa.Column("category_default", sa.String(length=128), nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.UniqueConstraint("provider_code", "merchant_key", name="uq_fuel_merchants_provider_key"),
            ),
        )
        create_index_if_not_exists(bind, "ix_fuel_merchants_provider", "fuel_merchants", ["provider_code"], schema=SCHEMA)

    if not table_exists(bind, "fuel_ingest_jobs", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fuel_ingest_jobs",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("provider_code", sa.String(length=64), nullable=False),
                sa.Column("client_id", sa.String(length=64), nullable=True),
                sa.Column("batch_ref", sa.String(length=128), nullable=True),
                sa.Column("idempotency_key", sa.String(length=128), nullable=False),
                sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column(
                    "status",
                    sa.Enum(*FUEL_INGEST_JOB_STATUS, name="fuel_ingest_job_status", native_enum=False),
                    nullable=False,
                ),
                sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
                sa.Column("inserted_count", sa.Integer(), nullable=False, server_default="0"),
                sa.Column("deduped_count", sa.Integer(), nullable=False, server_default="0"),
                sa.Column("error", sa.String(length=512), nullable=True),
                sa.Column("audit_event_id", sa.String(length=36), nullable=True),
            ),
        )
        create_unique_index_if_not_exists(
            bind,
            "uq_fuel_ingest_jobs_idempotency",
            "fuel_ingest_jobs",
            ["idempotency_key"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_ingest_jobs_provider_received",
            "fuel_ingest_jobs",
            ["provider_code", "received_at"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "fuel_limit_breaches", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fuel_limit_breaches",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("client_id", sa.String(length=64), nullable=False),
                sa.Column(
                    "scope_type",
                    sa.Enum(*FUEL_LIMIT_BREACH_SCOPE_TYPE, name="fuel_limit_breach_scope_type", native_enum=False),
                    nullable=False,
                ),
                sa.Column("scope_id", sa.String(length=36), nullable=False),
                sa.Column(
                    "period",
                    sa.Enum("DAILY", "WEEKLY", "MONTHLY", name="fuel_limit_period", native_enum=False),
                    nullable=False,
                ),
                sa.Column("limit_id", sa.String(length=36), nullable=False),
                sa.Column(
                    "breach_type",
                    sa.Enum(*FUEL_LIMIT_BREACH_TYPE, name="fuel_limit_breach_type", native_enum=False),
                    nullable=False,
                ),
                sa.Column("threshold", sa.Numeric(), nullable=False),
                sa.Column("observed", sa.Numeric(), nullable=False),
                sa.Column("delta", sa.Numeric(), nullable=False),
                sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("tx_id", sa.String(length=36), nullable=True),
                sa.Column(
                    "status",
                    sa.Enum(*FUEL_LIMIT_BREACH_STATUS, name="fuel_limit_breach_status", native_enum=False),
                    nullable=False,
                ),
                sa.Column("audit_event_id", sa.String(length=36), nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_limit_breaches_client",
            "fuel_limit_breaches",
            ["client_id"],
            schema=SCHEMA,
        )

    if table_exists(bind, "fuel_transactions", schema=SCHEMA):
        if not column_exists(bind, "fuel_transactions", "provider_code", schema=SCHEMA):
            op.add_column("fuel_transactions", sa.Column("provider_code", sa.String(length=64), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "fuel_transactions", "provider_tx_id", schema=SCHEMA):
            op.add_column("fuel_transactions", sa.Column("provider_tx_id", sa.String(length=128), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "fuel_transactions", "merchant_key", schema=SCHEMA):
            op.add_column("fuel_transactions", sa.Column("merchant_key", sa.String(length=256), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "fuel_transactions", "limit_check_status", schema=SCHEMA):
            op.add_column(
                "fuel_transactions",
                sa.Column(
                    "limit_check_status",
                    sa.Enum(*FUEL_LIMIT_CHECK_STATUS, name="fuel_limit_check_status", native_enum=False),
                    nullable=True,
                ),
                schema=SCHEMA,
            )
        if not column_exists(bind, "fuel_transactions", "limit_check_details", schema=SCHEMA):
            op.add_column("fuel_transactions", sa.Column("limit_check_details", sa.JSON(), nullable=True), schema=SCHEMA)
        create_index_if_not_exists(
            bind,
            "ix_fuel_transactions_provider_tx",
            "fuel_transactions",
            ["provider_code", "provider_tx_id"],
            schema=SCHEMA,
        )
        create_unique_index_if_not_exists(
            bind,
            "uq_fuel_transactions_provider_tx",
            "fuel_transactions",
            ["provider_code", "provider_tx_id"],
            schema=SCHEMA,
        )
        create_unique_index_if_not_exists(
            bind,
            "uq_fuel_transactions_provider_external_ref",
            "fuel_transactions",
            ["provider_code", "external_ref"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    pass
