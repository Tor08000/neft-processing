"""Add created_at column to cards

Revision ID: 20270720_0029_cards_created_at
Revises: 20270710_0028_limit_config_scope_enum_fix
Create Date: 2027-07-20 00:29:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import column_exists
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20270720_0029_cards_created_at"
down_revision = "20270710_0028_limit_config_scope_enum_fix"
branch_labels = None
depends_on = None

SCHEMA_RESOLUTION = resolve_db_schema()
SCHEMA = SCHEMA_RESOLUTION.schema


def upgrade() -> None:
    bind = op.get_bind()

    if not column_exists(bind, "cards", "created_at", schema=SCHEMA):
        op.add_column(
            "cards",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            schema=SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if column_exists(bind, "cards", "created_at", schema=SCHEMA):
        op.drop_column("cards", "created_at", schema=SCHEMA)
