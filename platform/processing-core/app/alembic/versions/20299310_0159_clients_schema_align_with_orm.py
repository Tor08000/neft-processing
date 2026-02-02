"""Align clients table with ORM model.

Revision ID: 20299310_0159_clients_schema_align_with_orm
Revises: 20299300_0158_clients_email
Create Date: 2026-04-18 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from alembic_helpers import DB_SCHEMA
from app.db.types import GUID


revision = "20299310_0159_clients_schema_align_with_orm"
down_revision = "20299300_0158_clients_email"
branch_labels = None
depends_on = None


def _missing_columns(inspector: sa.Inspector, table: str, expected: set[str]) -> set[str]:
    existing = {column["name"] for column in inspector.get_columns(table, schema=DB_SCHEMA)}
    return expected - existing


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    missing_columns = _missing_columns(
        inspector,
        "clients",
        {"full_name", "tariff_plan", "account_manager", "status", "client_offline_profile_id"},
    )

    if "full_name" in missing_columns:
        op.add_column(
            "clients",
            sa.Column("full_name", sa.String(), nullable=True),
            schema=DB_SCHEMA,
        )
    if "tariff_plan" in missing_columns:
        op.add_column(
            "clients",
            sa.Column("tariff_plan", sa.String(), nullable=True),
            schema=DB_SCHEMA,
        )
    if "account_manager" in missing_columns:
        op.add_column(
            "clients",
            sa.Column("account_manager", sa.String(), nullable=True),
            schema=DB_SCHEMA,
        )
    if "status" in missing_columns:
        op.add_column(
            "clients",
            sa.Column("status", sa.String(), nullable=True),
            schema=DB_SCHEMA,
        )
    if "client_offline_profile_id" in missing_columns:
        op.add_column(
            "clients",
            sa.Column("client_offline_profile_id", GUID(), nullable=True),
            schema=DB_SCHEMA,
        )


def downgrade() -> None:
    op.drop_column("clients", "client_offline_profile_id", schema=DB_SCHEMA)
    op.drop_column("clients", "status", schema=DB_SCHEMA)
    op.drop_column("clients", "account_manager", schema=DB_SCHEMA)
    op.drop_column("clients", "tariff_plan", schema=DB_SCHEMA)
    op.drop_column("clients", "full_name", schema=DB_SCHEMA)
