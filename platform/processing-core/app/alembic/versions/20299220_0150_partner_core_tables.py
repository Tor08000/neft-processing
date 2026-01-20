"""Add partner core tables.

Revision ID: 20299220_0150_partner_core_tables
Revises: 20299215_0149a_orgs_base
Create Date: 2026-02-28 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import DB_SCHEMA, create_table_if_not_exists, ensure_pg_enum, table_exists


revision = "20299220_0150_partner_core_tables"
down_revision = "20299215_0149a_orgs_base"
branch_labels = None
depends_on = None

PROFILE_STATUS = ("ONBOARDING", "ACTIVE", "SUSPENDED")
OFFER_STATUS = ("ACTIVE", "INACTIVE")
ORDER_STATUS = ("NEW", "ACCEPTED", "REJECTED", "IN_PROGRESS", "DONE")


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "partner_profile_status", PROFILE_STATUS, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "partner_offer_status", OFFER_STATUS, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "partner_order_status", ORDER_STATUS, schema=DB_SCHEMA)

    if not table_exists(bind, "partner_profiles", schema=DB_SCHEMA):
        create_table_if_not_exists(
            bind,
            "partner_profiles",
            schema=DB_SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("org_id", sa.BigInteger(), sa.ForeignKey(f"{DB_SCHEMA}.orgs.id"), nullable=False),
                sa.Column(
                    "status",
                    sa.Enum(*PROFILE_STATUS, name="partner_profile_status", native_enum=False),
                    nullable=False,
                    server_default="ONBOARDING",
                ),
                sa.Column("display_name", sa.String(length=255), nullable=True),
                sa.Column("contacts_json", postgresql.JSONB(none_as_null=True), nullable=True),
                sa.Column("meta_json", postgresql.JSONB(none_as_null=True), nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        op.create_index(
            "ix_partner_profiles_org_id",
            "partner_profiles",
            ["org_id"],
            unique=True,
            schema=DB_SCHEMA,
        )

    if not table_exists(bind, "partner_offers", schema=DB_SCHEMA):
        create_table_if_not_exists(
            bind,
            "partner_offers",
            schema=DB_SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("org_id", sa.BigInteger(), sa.ForeignKey(f"{DB_SCHEMA}.orgs.id"), nullable=False),
                sa.Column("code", sa.String(length=64), nullable=False),
                sa.Column("title", sa.String(length=255), nullable=False),
                sa.Column("description", sa.Text(), nullable=True),
                sa.Column("base_price", sa.Numeric(18, 2), nullable=True),
                sa.Column("currency", sa.String(length=8), nullable=False, server_default="RUB"),
                sa.Column(
                    "status",
                    sa.Enum(*OFFER_STATUS, name="partner_offer_status", native_enum=False),
                    nullable=False,
                    server_default="INACTIVE",
                ),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        op.create_index(
            "ix_partner_offers_org_status",
            "partner_offers",
            ["org_id", "status"],
            unique=False,
            schema=DB_SCHEMA,
        )
        op.create_unique_constraint(
            "uq_partner_offers_org_code",
            "partner_offers",
            ["org_id", "code"],
            schema=DB_SCHEMA,
        )

    if not table_exists(bind, "partner_orders", schema=DB_SCHEMA):
        create_table_if_not_exists(
            bind,
            "partner_orders",
            schema=DB_SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("partner_org_id", sa.BigInteger(), nullable=False),
                sa.Column("client_org_id", sa.BigInteger(), nullable=True),
                sa.Column("offer_id", sa.String(length=36), nullable=True),
                sa.Column("title", sa.String(length=255), nullable=False),
                sa.Column(
                    "status",
                    sa.Enum(*ORDER_STATUS, name="partner_order_status", native_enum=False),
                    nullable=False,
                    server_default="NEW",
                ),
                sa.Column("response_due_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("resolution_due_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        op.create_index(
            "ix_partner_orders_partner_status",
            "partner_orders",
            ["partner_org_id", "status"],
            unique=False,
            schema=DB_SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, "partner_orders", schema=DB_SCHEMA):
        op.drop_index("ix_partner_orders_partner_status", table_name="partner_orders", schema=DB_SCHEMA)
        op.drop_table("partner_orders", schema=DB_SCHEMA)
    if table_exists(bind, "partner_offers", schema=DB_SCHEMA):
        op.drop_constraint("uq_partner_offers_org_code", "partner_offers", type_="unique", schema=DB_SCHEMA)
        op.drop_index("ix_partner_offers_org_status", table_name="partner_offers", schema=DB_SCHEMA)
        op.drop_table("partner_offers", schema=DB_SCHEMA)
    if table_exists(bind, "partner_profiles", schema=DB_SCHEMA):
        op.drop_index("ix_partner_profiles_org_id", table_name="partner_profiles", schema=DB_SCHEMA)
        op.drop_table("partner_profiles", schema=DB_SCHEMA)
