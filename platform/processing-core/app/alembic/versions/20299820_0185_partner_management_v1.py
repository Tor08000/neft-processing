"""Partner management v1 tables.

Revision ID: 20299820_0185_partner_management_v1
Revises: 20299810_0184_event_outbox
Create Date: 2026-02-16 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import (
    DB_SCHEMA,
    column_exists,
    constraint_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    index_exists,
)
from db.types import GUID

revision = "20299820_0185_partner_management_v1"
down_revision = "20299810_0184_event_outbox"
branch_labels = None
depends_on = None


def _json_type(bind):
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def _partner_id_fk_type(bind) -> sa.types.TypeEngine:
    if bind.dialect.name != "postgresql":
        return sa.Text()

    partner_id_type = bind.execute(
        sa.text(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = 'partners'
              AND column_name = 'id'
            """
        ),
        {"schema": DB_SCHEMA},
    ).scalar_one_or_none()

    if partner_id_type == "uuid":
        return GUID()
    return sa.Text()


def upgrade() -> None:
    bind = op.get_bind()
    partner_fk_type = _partner_id_fk_type(bind)

    if not column_exists(bind, "partners", "code", schema=DB_SCHEMA):
        op.add_column("partners", sa.Column("code", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "partners", "legal_name", schema=DB_SCHEMA):
        op.add_column("partners", sa.Column("legal_name", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "partners", "brand_name", schema=DB_SCHEMA):
        op.add_column("partners", sa.Column("brand_name", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "partners", "partner_type", schema=DB_SCHEMA):
        op.add_column("partners", sa.Column("partner_type", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "partners", "inn", schema=DB_SCHEMA):
        op.add_column("partners", sa.Column("inn", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "partners", "ogrn", schema=DB_SCHEMA):
        op.add_column("partners", sa.Column("ogrn", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "partners", "contacts", schema=DB_SCHEMA):
        op.add_column("partners", sa.Column("contacts", _json_type(bind), nullable=False, server_default=sa.text("'{}'")), schema=DB_SCHEMA)
    if not column_exists(bind, "partners", "updated_at", schema=DB_SCHEMA):
        op.add_column("partners", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), schema=DB_SCHEMA)

    op.execute(sa.text(f"UPDATE {DB_SCHEMA}.partners SET legal_name = COALESCE(legal_name, name)"))
    op.execute(sa.text(f"UPDATE {DB_SCHEMA}.partners SET code = COALESCE(code, id::text)"))
    op.execute(sa.text(f"UPDATE {DB_SCHEMA}.partners SET partner_type = COALESCE(partner_type, 'OTHER')"))
    op.execute(sa.text(f"UPDATE {DB_SCHEMA}.partners SET status = UPPER(status)"))

    op.alter_column("partners", "code", nullable=False, schema=DB_SCHEMA)
    op.alter_column("partners", "legal_name", nullable=False, schema=DB_SCHEMA)
    op.alter_column("partners", "partner_type", nullable=False, schema=DB_SCHEMA)

    create_index_if_not_exists(bind, "uq_partners_code", "partners", ["code"], schema=DB_SCHEMA, unique=True)

    if not constraint_exists(bind, "partners", "ck_partners_partner_type_v1", schema=DB_SCHEMA):
        op.create_check_constraint(
            "ck_partners_partner_type_v1",
            "partners",
            "partner_type IN ('FUEL_NETWORK','MERCHANT','SERVICE_PROVIDER','EDO_PROVIDER','LOGISTICS_PROVIDER','OTHER')",
            schema=DB_SCHEMA,
        )
    if not constraint_exists(bind, "partners", "ck_partners_status_v1", schema=DB_SCHEMA):
        op.create_check_constraint(
            "ck_partners_status_v1",
            "partners",
            "status IN ('ACTIVE','INACTIVE','PENDING')",
            schema=DB_SCHEMA,
        )

    create_table_if_not_exists(
        bind,
        "partner_locations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("partner_id", partner_fk_type, sa.ForeignKey(f"{DB_SCHEMA}.partners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("lat", sa.Numeric(), nullable=True),
        sa.Column("lon", sa.Numeric(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_partner_locations_partner_id", "partner_locations", ["partner_id"], schema=DB_SCHEMA)
    create_index_if_not_exists(bind, "ix_partner_locations_partner_status", "partner_locations", ["partner_id", "status"], schema=DB_SCHEMA)
    if not index_exists(bind, "uq_partner_locations_partner_external", schema=DB_SCHEMA):
        op.create_index(
            "uq_partner_locations_partner_external",
            "partner_locations",
            ["partner_id", "external_id"],
            unique=True,
            schema=DB_SCHEMA,
            postgresql_where=sa.text("external_id IS NOT NULL"),
        )
    if not constraint_exists(bind, "partner_locations", "ck_partner_locations_status_v1", schema=DB_SCHEMA):
        op.create_check_constraint(
            "ck_partner_locations_status_v1",
            "partner_locations",
            "status IN ('ACTIVE','INACTIVE')",
            schema=DB_SCHEMA,
        )

    create_table_if_not_exists(
        bind,
        "partner_user_roles",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("partner_id", GUID(), sa.ForeignKey(f"{DB_SCHEMA}.partners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("roles", _json_type(bind), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_partner_user_roles_user_id", "partner_user_roles", ["user_id"], schema=DB_SCHEMA)
    create_index_if_not_exists(bind, "uq_partner_user_roles_partner_user", "partner_user_roles", ["partner_id", "user_id"], schema=DB_SCHEMA, unique=True)

    create_table_if_not_exists(
        bind,
        "partner_terms",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("partner_id", GUID(), sa.ForeignKey(f"{DB_SCHEMA}.partners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("terms", _json_type(bind), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(bind, "uq_partner_terms_partner_version", "partner_terms", ["partner_id", "version"], schema=DB_SCHEMA, unique=True)
    create_index_if_not_exists(bind, "ix_partner_terms_partner_status", "partner_terms", ["partner_id", "status"], schema=DB_SCHEMA)
    if not constraint_exists(bind, "partner_terms", "ck_partner_terms_status_v1", schema=DB_SCHEMA):
        op.create_check_constraint(
            "ck_partner_terms_status_v1",
            "partner_terms",
            "status IN ('DRAFT','ACTIVE','ARCHIVED')",
            schema=DB_SCHEMA,
        )


def downgrade() -> None:
    op.drop_table("partner_terms", schema=DB_SCHEMA)
    op.drop_table("partner_user_roles", schema=DB_SCHEMA)
    op.drop_table("partner_locations", schema=DB_SCHEMA)
