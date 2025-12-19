from __future__ import annotations

import psycopg

from tests.smoke.utils import assert_tables_exist, build_pg_dsn


def test_alembic_version_present_and_tables_exist():
    dsn = build_pg_dsn()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone() == (1,)

            cur.execute("SELECT count(*) FROM alembic_version")
            version_count = cur.fetchone()[0]
            assert version_count >= 1, "alembic_version table is empty"

        assert_tables_exist(conn, ["operations", "cards"])
