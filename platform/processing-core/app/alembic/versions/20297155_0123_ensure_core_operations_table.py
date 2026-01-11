"""Ensure operations table exists after bootstrap.

Revision ID: 20297155_0123_ensure_core_operations_table
Revises: 20297150_0122_marketplace_order_event_type_enum_update
Create Date: 2029-08-05 00:00:00.000000
"""

from __future__ import annotations

import importlib

from alembic import op

from app.alembic.helpers import is_postgres, regclass
from app.db.schema import quote_schema, resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20297155_0123_ensure_core_operations_table"
down_revision = "20297150_0122_marketplace_order_event_type_enum_update"
branch_labels = None
depends_on = None


def _operations_exists() -> bool:
    bind = op.get_bind()
    if not is_postgres(bind):
        return True

    schema = resolve_db_schema().schema
    qualified = f"{quote_schema(schema)}.operations"
    return regclass(bind, qualified) is not None


def upgrade() -> None:
    if _operations_exists():
        return

    base_tables = importlib.import_module(
        "app.alembic.versions.20297120_0117_create_core_base_tables_v1"
    )
    base_tables.upgrade()


def downgrade() -> None:
    raise RuntimeError("operations table guard migration cannot be safely downgraded")
