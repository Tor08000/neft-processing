# services/core-api/app/alembic/versions/20251118_0002_operations_journal.py

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.alembic.utils import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_index_if_exists,
    drop_table_if_exists,
)

# revision identifiers, used by Alembic.
revision = "20251118_0002_operations_journal"
down_revision = "20251112_0001_core"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    create_table_if_not_exists(
        bind,
        "operations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("operation_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("operation_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("merchant_id", sa.String(length=64), nullable=False),
        sa.Column("terminal_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("card_id", sa.String(length=64), nullable=False),
        sa.Column("accounts", JSONB, nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column(
            "authorized",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("response_code", sa.String(length=16), nullable=False),
        sa.Column("response_message", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("daily_limit", sa.BigInteger(), nullable=True),
        sa.Column("limit_per_tx", sa.BigInteger(), nullable=True),
        sa.Column("used_today", sa.BigInteger(), nullable=True),
        sa.Column("new_used_today", sa.BigInteger(), nullable=True),
        sa.Column("parent_operation_id", sa.String(length=64), nullable=True),
    )

    create_index_if_not_exists(bind, "ix_operations_card_id", "operations", ["card_id"])
    create_index_if_not_exists(bind, "ix_operations_client_id", "operations", ["client_id"])
    create_index_if_not_exists(bind, "ix_operations_merchant_id", "operations", ["merchant_id"])
    create_index_if_not_exists(bind, "ix_operations_terminal_id", "operations", ["terminal_id"])
    create_index_if_not_exists(bind, "ix_operations_created_at", "operations", ["created_at"])


def downgrade():
    bind = op.get_bind()
    drop_index_if_exists(bind, "ix_operations_created_at")
    drop_index_if_exists(bind, "ix_operations_terminal_id")
    drop_index_if_exists(bind, "ix_operations_merchant_id")
    drop_index_if_exists(bind, "ix_operations_client_id")
    drop_index_if_exists(bind, "ix_operations_card_id")
    drop_table_if_exists(bind, "operations")
