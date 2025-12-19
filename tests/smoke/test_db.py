from __future__ import annotations

import psycopg

from tests.smoke.utils import (
    assert_tables_exist,
    build_pg_dsn,
    qualified_regclass,
    schema_connect_kwargs,
    target_schema,
)


def test_alembic_version_present_and_tables_exist():
    dsn = build_pg_dsn()
    schema = target_schema()
    with psycopg.connect(dsn, **schema_connect_kwargs(schema)) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone() == (1,)

            cur.execute("SELECT to_regclass(%s)", (qualified_regclass("alembic_version", schema),))
            version_regclass = cur.fetchone()[0]
            assert version_regclass is not None, "alembic_version table is missing"

        assert_tables_exist(conn, ["operations", "cards"], schema=schema)
