"""Create user_clients mapping table.

Revision ID: 20251010_0001_user_clients
Revises: 20251003_0001_bootstrap_pwd_ver
Create Date: 2025-10-10 00:01:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251010_0001_user_clients"
down_revision = "20251003_0001_bootstrap_pwd_ver"
branch_labels = None
depends_on = None


AUTH_SCHEMA = "public"


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names(schema=AUTH_SCHEMA)


def upgrade() -> None:
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS public"))
    op.execute(sa.text("SET search_path TO public"))

    if not _table_exists("user_clients"):
        op.create_table(
            "user_clients",
            sa.Column(
                "user_id",
                sa.UUID(),
                sa.ForeignKey(f"{AUTH_SCHEMA}.users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("client_id", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            schema=AUTH_SCHEMA,
        )

    op.execute(
        sa.text(
            f'CREATE INDEX IF NOT EXISTS idx_user_clients_client_id ON "{AUTH_SCHEMA}".user_clients (client_id)'
        )
    )


def downgrade() -> None:
    if _table_exists("user_clients"):
        op.drop_table("user_clients", schema=AUTH_SCHEMA)
