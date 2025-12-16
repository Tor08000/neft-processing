"""add created_at to cards

Revision ID: 20251215_0005_add_created_at_to_cards
Revises: 20251208_0004a_bootstrap_clients_cards_partners
Create Date: 2025-12-15 00:05:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import column_exists, table_exists

# revision identifiers, used by Alembic.
revision = "20251215_0005_add_created_at_to_cards"
down_revision = "20251208_0004a_bootstrap_clients_cards_partners"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, "cards") and not column_exists(bind, "cards", "created_at"):
        op.add_column(
            "cards",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, "cards") and column_exists(bind, "cards", "created_at"):
        op.drop_column("cards", "created_at")
