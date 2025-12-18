# services/core-api/app/alembic/versions/20251118_0002_operations_journal.py

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.alembic.helpers import DB_SCHEMA, table_exists
from app.alembic.utils import create_index_if_not_exists, drop_index_if_exists, drop_table_if_exists

# revision identifiers, used by Alembic.
revision = "20251118_0002_operations_journal"
down_revision = "20251112_0001_core"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    schema = os.getenv("DB_SCHEMA", DB_SCHEMA)

    if not table_exists(bind, "operations", schema=schema):
        raise RuntimeError(
            "operations table must be created by 20251112_0001_core before 20251118_0002_operations_journal"
        )

    create_index_if_not_exists(bind, "ix_operations_card_id", "operations", ["card_id"], schema=schema)
    create_index_if_not_exists(bind, "ix_operations_client_id", "operations", ["client_id"], schema=schema)
    create_index_if_not_exists(bind, "ix_operations_merchant_id", "operations", ["merchant_id"], schema=schema)
    create_index_if_not_exists(bind, "ix_operations_terminal_id", "operations", ["terminal_id"], schema=schema)
    create_index_if_not_exists(bind, "ix_operations_created_at", "operations", ["created_at"], schema=schema)


def downgrade():
    bind = op.get_bind()
    schema = os.getenv("DB_SCHEMA", DB_SCHEMA)

    drop_index_if_exists(bind, "ix_operations_created_at", schema=schema)
    drop_index_if_exists(bind, "ix_operations_terminal_id", schema=schema)
    drop_index_if_exists(bind, "ix_operations_merchant_id", schema=schema)
    drop_index_if_exists(bind, "ix_operations_client_id", schema=schema)
    drop_index_if_exists(bind, "ix_operations_card_id", schema=schema)
    drop_table_if_exists(bind, "operations", schema=schema)
