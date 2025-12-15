from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection


MIN_VERSION_LENGTH = 128


def ensure_alembic_version_length(
    connection: Connection, *, min_length: int = MIN_VERSION_LENGTH
) -> None:
    """Ensure ``alembic_version.version_num`` can store long revision ids.

    The helper is intentionally idempotent and safe to call on every start.
    It only applies to PostgreSQL databases; other dialects are skipped.
    """

    if connection.dialect.name != "postgresql":
        return

    inspector = inspect(connection)
    if "alembic_version" not in inspector.get_table_names():
        connection.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR({min_length}) NOT NULL,
                    CONSTRAINT alembic_version_pkey PRIMARY KEY (version_num)
                )
                """
            )
        )
        return

    columns = inspector.get_columns("alembic_version")
    version_column = next((col for col in columns if col.get("name") == "version_num"), None)
    if version_column is None:
        connection.execute(
            text(
                f"""
                ALTER TABLE alembic_version
                ADD COLUMN version_num VARCHAR({min_length}) NOT NULL
                """
            )
        )
        current_length = None
    else:
        column_type = version_column.get("type")
        current_length = getattr(column_type, "length", None)

    if current_length is None or current_length < min_length:
        connection.execute(
            text(
                f"ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR({min_length})"
            )
        )

    pk = inspector.get_pk_constraint("alembic_version")
    pk_columns = set(pk.get("constrained_columns") or [])
    pk_name = pk.get("name")

    if pk_columns != {"version_num"}:
        if pk_name:
            connection.execute(
                text(
                    f'ALTER TABLE alembic_version DROP CONSTRAINT IF EXISTS "{pk_name}"'
                )
            )

        connection.execute(
            text(
                "ALTER TABLE alembic_version"
                " ADD CONSTRAINT alembic_version_pkey PRIMARY KEY (version_num)"
            )
        )
