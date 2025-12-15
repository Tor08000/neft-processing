"""Ensure client foreign keys use UUID"""

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261010_0012_client_ids_uuid"
down_revision = "20260115_0011_operations_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    _convert_to_uuid(connection, "clients", "id", set_default=True)

    for table in ("client_cards", "client_operations", "client_limits"):
        _convert_to_uuid(connection, table, "client_id")


def downgrade() -> None:
    connection = op.get_bind()

    for table in ("client_limits", "client_operations", "client_cards"):
        _convert_from_uuid(connection, table, "client_id")

    _convert_from_uuid(connection, "clients", "id", drop_default=True)


def _table_exists(connection, table: str) -> bool:
    result = connection.execute(
        sa.text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table}"},
    )
    return bool(result.scalar())


def _get_column_info(connection, table: str, column: str):
    return (
        connection.execute(
            sa.text(
                """
                SELECT data_type, udt_name, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table
                  AND column_name = :column
                """
            ),
            {"table": table, "column": column},
        )
        .mappings()
        .first()
    )


def _has_invalid_uuid_values(connection, table: str, column: str) -> bool:
    invalid_row = connection.execute(
        sa.text(
            f"""
            SELECT 1
            FROM "{table}"
            WHERE "{column}" IS NOT NULL
              AND NOT (
                "{column}"::text ~
                '^[0-9a-fA-F]{{8}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{12}}$'
              )
            LIMIT 1
            """
        )
    ).first()

    return bool(invalid_row)


def _convert_to_uuid(connection, table: str, column: str, *, set_default: bool = False) -> None:
    logger = context.get_context().log

    if not _table_exists(connection, table):
        logger.info("Skipping %s.%s: table missing", table, column)
        return

    column_info = _get_column_info(connection, table, column)
    if column_info is None:
        logger.info("Skipping %s.%s: column missing", table, column)
        return

    if column_info["udt_name"] == "uuid":
        logger.info("Skipping %s.%s: already uuid", table, column)
        if set_default and not column_info["column_default"]:
            op.execute(
                sa.text(
                    f"ALTER TABLE \"{table}\" ALTER COLUMN \"{column}\" SET DEFAULT gen_random_uuid()"
                )
            )
        return

    if _has_invalid_uuid_values(connection, table, column):
        logger.info("Skipping %s.%s: contains non-UUID values", table, column)
        return

    existing_type = sa.BigInteger() if column_info["data_type"] in {"bigint", "integer"} else sa.String()
    op.alter_column(
        table,
        column,
        existing_type=existing_type,
        type_=postgresql.UUID(as_uuid=True),
        postgresql_using=f'"{column}"::uuid',
        existing_nullable=column_info["is_nullable"] == "YES",
    )

    if set_default:
        op.execute(
            sa.text(
                f"ALTER TABLE \"{table}\" ALTER COLUMN \"{column}\" SET DEFAULT gen_random_uuid()"
            )
        )


def _convert_from_uuid(connection, table: str, column: str, *, drop_default: bool = False) -> None:
    logger = context.get_context().log

    if not _table_exists(connection, table):
        logger.info("Skipping downgrade for %s.%s: table missing", table, column)
        return

    column_info = _get_column_info(connection, table, column)
    if column_info is None:
        logger.info("Skipping downgrade for %s.%s: column missing", table, column)
        return

    if column_info["udt_name"] != "uuid":
        logger.info("Skipping downgrade for %s.%s: not uuid", table, column)
        return

    op.alter_column(
        table,
        column,
        existing_type=postgresql.UUID(as_uuid=True),
        type_=sa.BigInteger(),
        postgresql_using=f'"{column}"::text::bigint',
        existing_nullable=column_info["is_nullable"] == "YES",
    )

    if drop_default:
        op.execute(sa.text(f"ALTER TABLE \"{table}\" ALTER COLUMN \"{column}\" DROP DEFAULT"))
