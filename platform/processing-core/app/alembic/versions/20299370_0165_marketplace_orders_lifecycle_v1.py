"""Marketplace orders lifecycle v1 additions.

Revision ID: 20299370_0165_marketplace_orders_lifecycle_v1
Revises: 20299360_0164_marketplace_moderation_audit
Create Date: 2025-02-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import (
    DB_SCHEMA,
    column_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    ensure_pg_enum_value,
    safe_enum,
)
from db.types import GUID


revision = "20299370_0165_marketplace_orders_lifecycle_v1"
down_revision = "20299360_0164_marketplace_moderation_audit"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()

    for value in (
        "MARKETPLACE_ORDER_PAYMENT_PENDING",
        "MARKETPLACE_ORDER_PAYMENT_PAID",
        "MARKETPLACE_ORDER_CONFIRMED",
        "MARKETPLACE_ORDER_DECLINED",
    ):
        ensure_pg_enum_value(bind, "case_event_type", value, schema=DB_SCHEMA)

    for value in (
        "PENDING_PAYMENT",
        "PAID",
        "CONFIRMED_BY_PARTNER",
        "CLOSED",
        "DECLINED_BY_PARTNER",
        "CANCELED_BY_CLIENT",
        "PAYMENT_FAILED",
    ):
        ensure_pg_enum_value(bind, "marketplace_order_status", value, schema=DB_SCHEMA)

    for value in (
        "CREATED",
        "PAYMENT_PENDING",
        "PAYMENT_PAID",
        "PAYMENT_FAILED",
        "CONFIRMED",
        "DECLINED",
        "COMPLETED",
        "CANCELED",
        "NOTE",
    ):
        ensure_pg_enum_value(bind, "marketplace_order_event_type", value, schema=DB_SCHEMA)

    ensure_pg_enum(
        bind,
        "marketplace_order_payment_status",
        ["UNPAID", "AUTHORIZED", "PAID", "FAILED", "REFUNDED"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_order_payment_method",
        ["NEFT_INTERNAL", "EXTERNAL_STUB"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_order_line_subject_type",
        ["PRODUCT", "SERVICE"],
        schema=DB_SCHEMA,
    )
    ensure_pg_enum(
        bind,
        "marketplace_order_proof_kind",
        ["PHOTO", "PDF", "ACT", "CHECK", "OTHER"],
        schema=DB_SCHEMA,
    )

    payment_status_enum = safe_enum(
        bind,
        "marketplace_order_payment_status",
        ["UNPAID", "AUTHORIZED", "PAID", "FAILED", "REFUNDED"],
        schema=DB_SCHEMA,
    )
    payment_method_enum = safe_enum(
        bind,
        "marketplace_order_payment_method",
        ["NEFT_INTERNAL", "EXTERNAL_STUB"],
        schema=DB_SCHEMA,
    )
    line_subject_enum = safe_enum(
        bind,
        "marketplace_order_line_subject_type",
        ["PRODUCT", "SERVICE"],
        schema=DB_SCHEMA,
    )
    proof_kind_enum = safe_enum(
        bind,
        "marketplace_order_proof_kind",
        ["PHOTO", "PDF", "ACT", "CHECK", "OTHER"],
        schema=DB_SCHEMA,
    )
    status_enum = safe_enum(
        bind,
        "marketplace_order_status",
        [
            "CREATED",
            "ACCEPTED",
            "REJECTED",
            "IN_PROGRESS",
            "COMPLETED",
            "FAILED",
            "CANCELLED",
            "PENDING_PAYMENT",
            "PAID",
            "CONFIRMED_BY_PARTNER",
            "CLOSED",
            "DECLINED_BY_PARTNER",
            "CANCELED_BY_CLIENT",
            "PAYMENT_FAILED",
        ],
        schema=DB_SCHEMA,
    )

    if not column_exists(bind, "marketplace_orders", "currency", schema=DB_SCHEMA):
        op.add_column("marketplace_orders", sa.Column("currency", sa.String(length=8)), schema=DB_SCHEMA)
    if not column_exists(bind, "marketplace_orders", "subtotal_amount", schema=DB_SCHEMA):
        op.add_column("marketplace_orders", sa.Column("subtotal_amount", sa.Numeric(18, 4)), schema=DB_SCHEMA)
    if not column_exists(bind, "marketplace_orders", "discount_amount", schema=DB_SCHEMA):
        op.add_column("marketplace_orders", sa.Column("discount_amount", sa.Numeric(18, 4)), schema=DB_SCHEMA)
    if not column_exists(bind, "marketplace_orders", "total_amount", schema=DB_SCHEMA):
        op.add_column("marketplace_orders", sa.Column("total_amount", sa.Numeric(18, 4)), schema=DB_SCHEMA)
    if not column_exists(bind, "marketplace_orders", "payment_status", schema=DB_SCHEMA):
        op.add_column(
            "marketplace_orders",
            sa.Column("payment_status", payment_status_enum, nullable=True),
            schema=DB_SCHEMA,
        )
    if not column_exists(bind, "marketplace_orders", "payment_method", schema=DB_SCHEMA):
        op.add_column(
            "marketplace_orders",
            sa.Column("payment_method", payment_method_enum, nullable=True),
            schema=DB_SCHEMA,
        )
    if not column_exists(bind, "marketplace_orders", "meta", schema=DB_SCHEMA):
        op.add_column("marketplace_orders", sa.Column("meta", JSON_TYPE, nullable=True), schema=DB_SCHEMA)

    if not column_exists(bind, "marketplace_order_events", "before_status", schema=DB_SCHEMA):
        op.add_column(
            "marketplace_order_events",
            sa.Column("before_status", status_enum, nullable=True),
            schema=DB_SCHEMA,
        )
    if not column_exists(bind, "marketplace_order_events", "after_status", schema=DB_SCHEMA):
        op.add_column(
            "marketplace_order_events",
            sa.Column("after_status", status_enum, nullable=True),
            schema=DB_SCHEMA,
        )
    if not column_exists(bind, "marketplace_order_events", "reason_code", schema=DB_SCHEMA):
        op.add_column("marketplace_order_events", sa.Column("reason_code", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "marketplace_order_events", "comment", schema=DB_SCHEMA):
        op.add_column("marketplace_order_events", sa.Column("comment", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "marketplace_order_events", "meta", schema=DB_SCHEMA):
        op.add_column("marketplace_order_events", sa.Column("meta", JSON_TYPE, nullable=True), schema=DB_SCHEMA)

    create_table_if_not_exists(
        bind,
        "marketplace_order_lines",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("order_id", GUID(), nullable=False),
        sa.Column("offer_id", GUID(), nullable=False),
        sa.Column("subject_type", line_subject_enum, nullable=False),
        sa.Column("subject_id", GUID(), nullable=False),
        sa.Column("title_snapshot", sa.Text(), nullable=False),
        sa.Column("qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("line_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("meta", JSON_TYPE, nullable=True),
        sa.ForeignKeyConstraint(
            ["order_id"],
            [f"{DB_SCHEMA + '.' if DB_SCHEMA else ''}marketplace_orders.id"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_order_lines_order_id",
        "marketplace_order_lines",
        ["order_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_order_lines_offer_id",
        "marketplace_order_lines",
        ["offer_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_order_proofs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("order_id", GUID(), nullable=False),
        sa.Column("kind", proof_kind_enum, nullable=False),
        sa.Column("attachment_id", GUID(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("meta", JSON_TYPE, nullable=True),
        sa.ForeignKeyConstraint(
            ["order_id"],
            [f"{DB_SCHEMA + '.' if DB_SCHEMA else ''}marketplace_orders.id"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_order_proofs_order_id",
        "marketplace_order_proofs",
        ["order_id"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    pass
