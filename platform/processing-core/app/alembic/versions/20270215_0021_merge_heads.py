"""Merge multiple heads into single branch.

Revision ID: 20270215_0021_merge_heads
Revises: 20260110_0009_create_clearing_table, 20260701_0009_client_portal, 20270115_0020, 20270201_0020
Create Date: 2027-02-15 00:00:00
"""

from __future__ import annotations

from alembic import op

from app.alembic.helpers import DB_SCHEMA, table_exists
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20270215_0021_merge_heads"
down_revision = (
    "20260110_0009_create_clearing_table",
    "20260701_0009_client_portal",
    "20270115_0020",
    "20270201_0020",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge node with sanity checks.

    The migration remains structurally a merge, but it now asserts that the
    core tables exist so the upgrade cannot silently succeed while skipping the
    required bootstrap DDL.
    """

    bind = op.get_bind()
    schema_resolution = resolve_db_schema()
    schema = schema_resolution.target_schema
    print(f"[{revision}] {schema_resolution.line()}")

    missing = [name for name in ("operations", "accounts", "ledger_entries", "limit_configs") if not table_exists(bind, name, schema=schema)]
    if missing:
        raise RuntimeError(
            "Merge revision 20270215_0021_merge_heads requires core tables to exist; missing: "
            + ", ".join(missing)
        )


def downgrade() -> None:
    raise RuntimeError("Merge revision 20270215_0021_merge_heads cannot be downgraded safely")
