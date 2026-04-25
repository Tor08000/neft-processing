"""Repair legacy ledger_entries schema drift for posting runtime.

Revision ID: 20300200_0213_ledger_entries_runtime_repair
Revises: 20300195_0212_account_balances_hold_balance
Create Date: 2030-01-19 01:10:00.000000
"""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from alembic_helpers import (
    DB_SCHEMA,
    column_exists,
    create_index_if_not_exists,
    create_unique_index_if_not_exists,
    table_exists,
)
from db.types import GUID


revision = "20300200_0213_ledger_entries_runtime_repair"
down_revision = "20300195_0212_account_balances_hold_balance"
branch_labels = None
depends_on = None

SCHEMA_PREFIX = f"{DB_SCHEMA}." if DB_SCHEMA else ""


def _backfill_entry_ids_sqlite(bind) -> None:
    missing_ids = bind.execute(
        sa.text(f"SELECT id FROM {SCHEMA_PREFIX}ledger_entries WHERE entry_id IS NULL")
    ).scalars()
    for row_id in missing_ids:
        bind.execute(
            sa.text(f"UPDATE {SCHEMA_PREFIX}ledger_entries SET entry_id = :entry_id WHERE id = :row_id"),
            {"entry_id": str(uuid5(NAMESPACE_URL, f"ledger-entry:{row_id}")), "row_id": row_id},
        )


def upgrade() -> None:
    bind = op.get_bind()

    if not table_exists(bind, "ledger_entries", schema=DB_SCHEMA):
        return

    if not column_exists(bind, "ledger_entries", "entry_id", schema=DB_SCHEMA):
        op.add_column(
            "ledger_entries",
            sa.Column("entry_id", GUID(), nullable=True),
            schema=DB_SCHEMA,
        )
    if not column_exists(bind, "ledger_entries", "balance_before", schema=DB_SCHEMA):
        op.add_column(
            "ledger_entries",
            sa.Column("balance_before", sa.Numeric(18, 4), nullable=True),
            schema=DB_SCHEMA,
        )
    if not column_exists(bind, "ledger_entries", "metadata", schema=DB_SCHEMA):
        op.add_column(
            "ledger_entries",
            sa.Column("metadata", sa.JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True),
            schema=DB_SCHEMA,
        )

    if bind.dialect.name == "postgresql":
        op.execute(
            f"""
            UPDATE {SCHEMA_PREFIX}ledger_entries
            SET entry_id = (
                substr(md5('ledger-entry:' || id::text), 1, 8) || '-' ||
                substr(md5('ledger-entry:' || id::text), 9, 4) || '-' ||
                substr(md5('ledger-entry:' || id::text), 13, 4) || '-' ||
                substr(md5('ledger-entry:' || id::text), 17, 4) || '-' ||
                substr(md5('ledger-entry:' || id::text), 21, 12)
            )::uuid
            WHERE entry_id IS NULL
            """
        )
    else:
        _backfill_entry_ids_sqlite(bind)

    op.alter_column(
        "ledger_entries",
        "entry_id",
        existing_type=GUID(),
        nullable=False,
        schema=DB_SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_ledger_entries_entry_id",
        "ledger_entries",
        ["entry_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_ledger_entries_posting_id",
        "ledger_entries",
        ["posting_id"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    # Keep runtime repair additive-only; legacy ledgers may already rely on the new columns.
    pass
