"""Repair ledger_entries.operation_id to point at canonical operations.id.

Revision ID: 20300210_0214_ledger_entries_operation_fk_repair
Revises: 20300200_0213_ledger_entries_runtime_repair
Create Date: 2030-01-19 01:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, column_exists, constraint_exists, table_exists
from db.types import GUID


revision = "20300210_0214_ledger_entries_operation_fk_repair"
down_revision = "20300200_0213_ledger_entries_runtime_repair"
branch_labels = None
depends_on = None

SCHEMA_PREFIX = f"{DB_SCHEMA}." if DB_SCHEMA else ""
UUID_REGEX = "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"


def _column_udt(bind, table_name: str, column_name: str) -> str | None:
    return bind.execute(
        sa.text(
            """
            SELECT udt_name
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :table_name AND column_name = :column_name
            """
        ),
        {"schema": DB_SCHEMA, "table_name": table_name, "column_name": column_name},
    ).scalar_one_or_none()


def upgrade() -> None:
    bind = op.get_bind()

    if not table_exists(bind, "ledger_entries", schema=DB_SCHEMA):
        return
    if not column_exists(bind, "ledger_entries", "operation_id", schema=DB_SCHEMA):
        return

    if bind.dialect.name == "postgresql":
        op.execute(
            f"""
            UPDATE {SCHEMA_PREFIX}ledger_entries AS le
            SET operation_id = o.id::text
            FROM {SCHEMA_PREFIX}operations AS o
            WHERE le.operation_id IS NOT NULL
              AND le.operation_id <> ''
              AND le.operation_id = o.operation_id::text
              AND le.operation_id <> o.id::text
            """
        )

        invalid_count = bind.execute(
            sa.text(
                f"""
                SELECT COUNT(*)
                FROM {SCHEMA_PREFIX}ledger_entries
                WHERE operation_id IS NOT NULL
                  AND operation_id <> ''
                  AND operation_id !~* :uuid_regex
                """
            ),
            {"uuid_regex": UUID_REGEX},
        ).scalar_one()
        if invalid_count:
            raise RuntimeError(
                f"ledger_entries.operation_id still contains {invalid_count} non-UUID legacy values after mapping"
            )

    if constraint_exists(bind, "ledger_entries", "ledger_entries_operation_id_fkey", schema=DB_SCHEMA):
        op.drop_constraint(
            "ledger_entries_operation_id_fkey",
            "ledger_entries",
            schema=DB_SCHEMA,
            type_="foreignkey",
        )

    if bind.dialect.name == "postgresql" and _column_udt(bind, "ledger_entries", "operation_id") != "uuid":
        op.alter_column(
            "ledger_entries",
            "operation_id",
            existing_type=sa.String(length=64),
            type_=GUID(),
            postgresql_using="NULLIF(operation_id, '')::uuid",
            schema=DB_SCHEMA,
        )

    if not constraint_exists(bind, "ledger_entries", "ledger_entries_operation_id_fkey", schema=DB_SCHEMA):
        op.create_foreign_key(
            "ledger_entries_operation_id_fkey",
            "ledger_entries",
            "operations",
            ["operation_id"],
            ["id"],
            source_schema=DB_SCHEMA,
            referent_schema=DB_SCHEMA,
            ondelete="SET NULL",
        )


def downgrade() -> None:
    # Keep runtime repair forward-only; reverting would reintroduce legacy FK drift.
    pass
