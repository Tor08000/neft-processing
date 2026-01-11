"""Fix operations.client_id type to VARCHAR(64).

Revision ID: 20297160_0124_fix_operations_client_id_type
Revises: 20297155_0123_ensure_core_operations_table
Create Date: 2029-08-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.helpers import is_postgres
from app.alembic.utils import SCHEMA

# revision identifiers, used by Alembic.
revision = "20297160_0124_fix_operations_client_id_type"
down_revision = "20297155_0123_ensure_core_operations_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return
    inspector = sa.inspect(bind)
    if "operations" not in inspector.get_table_names(schema=SCHEMA):
        return
    columns = {col["name"]: col for col in inspector.get_columns("operations", schema=SCHEMA)}
    client_col = columns.get("client_id")
    if client_col is None:
        return
    col_type = client_col.get("type")
    if isinstance(col_type, postgresql.UUID):
        op.execute(
            sa.text(
                f'ALTER TABLE "{SCHEMA}".operations '
                "ALTER COLUMN client_id TYPE VARCHAR(64) USING client_id::text"
            )
        )


def downgrade() -> None:
    raise RuntimeError("operations.client_id type fix cannot be safely downgraded")
