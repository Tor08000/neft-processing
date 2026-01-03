"""Marketplace orders v1.

Revision ID: 20292010_0108_marketplace_orders_v1
Revises: 20292000_0107_marketplace_catalog_v1
Create Date: 2026-02-05 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from app.alembic.helpers import (
    DB_SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_expr_index_if_not_exists,
    ensure_pg_enum,
    ensure_pg_enum_value,
    is_postgres,
    safe_enum,
)
from app.db.types import GUID


revision = "20292010_0108_marketplace_orders_v1"
down_revision = "20292000_0107_marketplace_catalog_v1"
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

    ensure_pg_enum(
        bind,
        "marketplace_order_status",
        ["CREATED", "ACCEPTED", "REJECTED", "IN_PROGRESS", "COMPLETED", "FAILED", "CANCELLED"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_order_event_type",
        [
            "ORDER_CREATED",
            "ORDER_ACCEPTED",
            "ORDER_REJECTED",
            "ORDER_STARTED",
            "ORDER_PROGRESS_UPDATED",
            "ORDER_COMPLETED",
            "ORDER_FAILED",
            "ORDER_CANCELLED",
            "ORDER_NOTE_ADDED",
        ],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_order_actor_type",
        ["client", "partner", "admin", "system"],
        schema=DB_SCHEMA,
    )

    for value in (
        "MARKETPLACE_ORDER_CREATED",
        "MARKETPLACE_ORDER_ACCEPTED",
        "MARKETPLACE_ORDER_REJECTED",
        "MARKETPLACE_ORDER_STARTED",
        "MARKETPLACE_ORDER_PROGRESS_UPDATED",
        "MARKETPLACE_ORDER_COMPLETED",
        "MARKETPLACE_ORDER_FAILED",
        "MARKETPLACE_ORDER_CANCELLED",
    ):
        ensure_pg_enum_value(bind, "case_event_type", value, schema=DB_SCHEMA)

    create_table_if_not_exists(
        bind,
        "marketplace_orders",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("client_id", GUID(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("product_id", GUID(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("price_snapshot", JSON_TYPE, nullable=False),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "marketplace_order_status",
                ["CREATED", "ACCEPTED", "REJECTED", "IN_PROGRESS", "COMPLETED", "FAILED", "CANCELLED"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_event_id", sa.String(length=36), nullable=True),
        sa.Column("external_ref", sa.Text(), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_orders_client_created",
        "marketplace_orders",
        ["client_id", "created_at"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_orders_partner_created",
        "marketplace_orders",
        ["partner_id", "created_at"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_orders_status_created",
        "marketplace_orders",
        ["status", "created_at"],
        schema=DB_SCHEMA,
    )
    create_unique_expr_index_if_not_exists(
        bind,
        "ux_marketplace_orders_client_external_ref",
        "marketplace_orders",
        "(client_id, external_ref) WHERE external_ref IS NOT NULL",
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_order_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("order_id", GUID(), nullable=False),
        sa.Column(
            "event_type",
            safe_enum(
                bind,
                "marketplace_order_event_type",
                [
                    "ORDER_CREATED",
                    "ORDER_ACCEPTED",
                    "ORDER_REJECTED",
                    "ORDER_STARTED",
                    "ORDER_PROGRESS_UPDATED",
                    "ORDER_COMPLETED",
                    "ORDER_FAILED",
                    "ORDER_CANCELLED",
                    "ORDER_NOTE_ADDED",
                ],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("payload_redacted", JSON_TYPE, nullable=False),
        sa.Column(
            "actor_type",
            safe_enum(
                bind,
                "marketplace_order_actor_type",
                ["client", "partner", "admin", "system"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("actor_id", GUID(), nullable=True),
        sa.Column("audit_event_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["order_id"],
            [f"{_schema_prefix()}marketplace_orders.id"],
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
        "ix_marketplace_order_events_order_occurred",
        "marketplace_order_events",
        ["order_id", "occurred_at"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_order_events_order_type",
        "marketplace_order_events",
        ["order_id", "event_type"],
        schema=DB_SCHEMA,
    )

    _create_worm_guard("marketplace_order_events")


def downgrade() -> None:
    pass
