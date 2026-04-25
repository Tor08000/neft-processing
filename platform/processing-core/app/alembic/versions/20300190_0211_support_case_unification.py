"""Add unified support/case owner fields and lifecycle parity.

Revision ID: 20300190_0211_support_case_unification
Revises: 20300180_0210
Create Date: 2030-01-19 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, column_exists, create_index_if_not_exists, ensure_pg_enum_value
from db.types import GUID


revision = "20300190_0211_support_case_unification"
down_revision = "20300180_0210"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    for value in ("support", "dispute", "incident"):
        ensure_pg_enum_value(bind, "case_kind", value, schema=DB_SCHEMA)
    ensure_pg_enum_value(bind, "case_status", "WAITING", schema=DB_SCHEMA)

    if not column_exists(bind, "cases", "entity_type", schema=DB_SCHEMA):
        op.add_column("cases", sa.Column("entity_type", sa.String(length=64), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "cases", "description", schema=DB_SCHEMA):
        op.add_column("cases", sa.Column("description", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "cases", "client_id", schema=DB_SCHEMA):
        op.add_column("cases", sa.Column("client_id", sa.String(length=64), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "cases", "partner_id", schema=DB_SCHEMA):
        op.add_column("cases", sa.Column("partner_id", sa.String(length=64), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "cases", "case_source_ref_type", schema=DB_SCHEMA):
        op.add_column("cases", sa.Column("case_source_ref_type", sa.String(length=64), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "cases", "case_source_ref_id", schema=DB_SCHEMA):
        op.add_column("cases", sa.Column("case_source_ref_id", GUID(), nullable=True), schema=DB_SCHEMA)

    create_index_if_not_exists(bind, "ix_cases_entity_type", "cases", ["entity_type"], schema=DB_SCHEMA)
    create_index_if_not_exists(bind, "ix_cases_client_id", "cases", ["client_id"], schema=DB_SCHEMA)
    create_index_if_not_exists(bind, "ix_cases_partner_id", "cases", ["partner_id"], schema=DB_SCHEMA)
    create_index_if_not_exists(bind, "ix_cases_case_source_ref_type", "cases", ["case_source_ref_type"], schema=DB_SCHEMA)
    create_index_if_not_exists(bind, "ix_cases_case_source_ref_id", "cases", ["case_source_ref_id"], schema=DB_SCHEMA)


def downgrade() -> None:
    # Keep migration additive-only to avoid destructive support/case rollback.
    pass
