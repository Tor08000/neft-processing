"""Align document status lifecycle with legal finalization.

Revision ID: 20290501_0045_document_status_lifecycle
Revises: 20280415_0044_accounting_export_batches
Create Date: 2029-05-01 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import column_exists, ensure_pg_enum, enum_exists, is_postgres, table_exists
from app.db.schema import resolve_db_schema


# revision identifiers, used by Alembic.
revision = "20290501_0045_document_status_lifecycle"
down_revision = "20280415_0044_accounting_export_batches"
branch_labels = None
depends_on = None

DOCUMENT_STATUSES = ["DRAFT", "ISSUED", "ACKNOWLEDGED", "FINALIZED", "VOID"]
CLOSING_PACKAGE_STATUSES = ["DRAFT", "ISSUED", "ACKNOWLEDGED", "FINALIZED", "VOID"]


def _schema_name(schema: str | None) -> str:
    return schema or "public"


def _qualify(name: str, schema: str) -> str:
    return f'"{schema}"."{name}"'


def _column_type(bind, schema: str, table_name: str, column_name: str) -> tuple[str | None, str | None, str | None]:
    result = bind.execute(
        sa.text(
            """
            SELECT data_type, udt_name, udt_schema
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :table_name AND column_name = :column_name
            """
        ),
        {"schema": schema, "table_name": table_name, "column_name": column_name},
    ).first()
    if result is None:
        return None, None, None
    return result[0], result[1], result[2]


def _enum_labels(bind, schema: str, enum_name: str) -> list[str]:
    result = bind.execute(
        sa.text(
            """
            SELECT e.enumlabel
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            JOIN pg_enum e ON e.enumtypid = t.oid
            WHERE n.nspname = :schema AND t.typname = :enum_name
            ORDER BY e.enumsortorder
            """
        ),
        {"schema": schema, "enum_name": enum_name},
    ).all()
    return [row[0] for row in result]


def _enum_in_use(bind, schema: str, enum_name: str) -> bool:
    result = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE udt_schema = :schema AND udt_name = :enum_name
            LIMIT 1
            """
        ),
        {"schema": schema, "enum_name": enum_name},
    ).first()
    return result is not None


def _ensure_enum_with_recreate(
    bind, schema: str, enum_name: str, values: list[str]
) -> None:
    enum_schema = _schema_name(schema)
    old_enum_name = f"{enum_name}_old"
    enum_exists_now = enum_exists(bind, enum_name, schema=enum_schema)
    old_enum_exists = enum_exists(bind, old_enum_name, schema=enum_schema)

    if not enum_exists_now:
        ensure_pg_enum(bind, enum_name, values=values, schema=enum_schema)
        return

    current_labels = _enum_labels(bind, enum_schema, enum_name)
    if current_labels == values:
        return

    if not old_enum_exists:
        bind.execute(
            sa.text(
                f'ALTER TYPE { _qualify(enum_name, enum_schema) } RENAME TO "{old_enum_name}"'
            )
        )
        old_enum_exists = True
    elif not _enum_in_use(bind, enum_schema, old_enum_name):
        bind.execute(sa.text(f"DROP TYPE {_qualify(old_enum_name, enum_schema)}"))
        bind.execute(
            sa.text(
                f'ALTER TYPE { _qualify(enum_name, enum_schema) } RENAME TO "{old_enum_name}"'
            )
        )
        old_enum_exists = True

    if not enum_exists(bind, enum_name, schema=enum_schema):
        ensure_pg_enum(bind, enum_name, values=values, schema=enum_schema)

    if old_enum_exists and not _enum_in_use(bind, enum_schema, old_enum_name):
        bind.execute(sa.text(f"DROP TYPE {_qualify(old_enum_name, enum_schema)}"))


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    schema = resolve_db_schema().schema
    enum_schema = _schema_name(schema)

    _ensure_enum_with_recreate(bind, enum_schema, "document_status", DOCUMENT_STATUSES)
    _ensure_enum_with_recreate(
        bind, enum_schema, "closing_package_status", CLOSING_PACKAGE_STATUSES
    )

    if table_exists(bind, "documents", schema=enum_schema) and column_exists(
        bind, "documents", "status", schema=enum_schema
    ):
        data_type, udt_name, udt_schema = _column_type(
            bind, enum_schema, "documents", "status"
        )
        if not (
            data_type == "USER-DEFINED"
            and udt_name == "document_status"
            and udt_schema == enum_schema
        ):
            bind.execute(
                sa.text(
                    "ALTER TABLE {table} "
                    "ALTER COLUMN status TYPE {enum} "
                    "USING (CASE "
                    "WHEN status IS NULL THEN 'DRAFT' "
                    "WHEN status::text = 'GENERATED' THEN 'ISSUED' "
                    "WHEN status::text = 'SENT' THEN 'ISSUED' "
                    "WHEN status::text = 'CANCELLED' THEN 'VOID' "
                    "ELSE status::text END)::text::{enum}".format(
                        table=_qualify("documents", enum_schema),
                        enum=_qualify("document_status", enum_schema),
                    )
                )
            )
            bind.execute(
                sa.text(
                    "ALTER TABLE {table} ALTER COLUMN status SET DEFAULT 'DRAFT'".format(
                        table=_qualify("documents", enum_schema)
                    )
                )
            )

    if table_exists(bind, "closing_packages", schema=enum_schema) and column_exists(
        bind, "closing_packages", "status", schema=enum_schema
    ):
        data_type, udt_name, udt_schema = _column_type(
            bind, enum_schema, "closing_packages", "status"
        )
        if not (
            data_type == "USER-DEFINED"
            and udt_name == "closing_package_status"
            and udt_schema == enum_schema
        ):
            bind.execute(
                sa.text(
                    "ALTER TABLE {table} "
                    "ALTER COLUMN status TYPE {enum} "
                    "USING (CASE "
                    "WHEN status IS NULL THEN 'DRAFT' "
                    "WHEN status::text = 'GENERATED' THEN 'ISSUED' "
                    "WHEN status::text = 'SENT' THEN 'ISSUED' "
                    "WHEN status::text = 'CANCELLED' THEN 'VOID' "
                    "ELSE status::text END)::text::{enum}".format(
                        table=_qualify("closing_packages", enum_schema),
                        enum=_qualify("closing_package_status", enum_schema),
                    )
                )
            )
            bind.execute(
                sa.text(
                    "ALTER TABLE {table} ALTER COLUMN status SET DEFAULT 'DRAFT'".format(
                        table=_qualify("closing_packages", enum_schema)
                    )
                )
            )

    for enum_name in ("document_status_old", "closing_package_status_old"):
        if enum_exists(bind, enum_name, schema=enum_schema) and not _enum_in_use(
            bind, enum_schema, enum_name
        ):
            bind.execute(sa.text(f"DROP TYPE {_qualify(enum_name, enum_schema)}"))


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
