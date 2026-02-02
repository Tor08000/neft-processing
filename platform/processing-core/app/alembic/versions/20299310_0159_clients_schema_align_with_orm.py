"""Align clients table with ORM model.

Revision ID: 20299310_0159_clients_schema_align_with_orm
Revises: 20299300_0158_clients_email
Create Date: 2026-04-18 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA
from app.db.types import GUID


revision = "20299310_0159_clients_schema_align_with_orm"
down_revision = "20299300_0158_clients_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("full_name", sa.String(), nullable=True),
        schema=DB_SCHEMA,
    )
    op.add_column(
        "clients",
        sa.Column("client_offline_profile_id", GUID(), nullable=True),
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("clients", "client_offline_profile_id", schema=DB_SCHEMA)
    op.drop_column("clients", "full_name", schema=DB_SCHEMA)
