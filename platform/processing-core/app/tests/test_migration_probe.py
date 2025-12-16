import sqlalchemy as sa
import pytest

from app.db import engine


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Probe requires Postgres database")
def test_postgres_probe_creates_table_and_is_visible():
    table_name = "_probe_migrations"
    schema = "public"

    with engine.begin() as connection:
        connection.exec_driver_sql(f"DROP TABLE IF EXISTS {schema}.{table_name}")
        connection.exec_driver_sql(
            f"""
            CREATE TABLE {schema}.{table_name} (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )

        try:
            result = connection.execute(
                sa.text(
                    """
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = :schema
                      AND tablename = :table_name
                    """
                ),
                {"schema": schema, "table_name": table_name},
            ).scalar()

            inspector = sa.inspect(connection)
            assert table_name in inspector.get_table_names(schema=schema)
            assert result == table_name
        finally:
            connection.exec_driver_sql(f"DROP TABLE IF EXISTS {schema}.{table_name}")
