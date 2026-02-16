"""create logistics_idempotency_keys

Revision ID: 202602160001
Revises: 
Create Date: 2026-02-16 00:01:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202602160001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "logistics_idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "key", name="uq_logistics_idempotency_scope_key"),
    )
    op.create_index("ix_logistics_idempotency_created_at", "logistics_idempotency_keys", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_logistics_idempotency_created_at", table_name="logistics_idempotency_keys")
    op.drop_table("logistics_idempotency_keys")
