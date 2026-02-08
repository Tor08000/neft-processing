from __future__ import annotations

import os


def get_test_dsn_or_fail() -> str:
    dsn = (os.getenv("TEST_DATABASE_DSN") or "").strip()
    if not dsn:
        dsn = (os.getenv("DATABASE_URL_TEST") or "").strip()
    if not dsn:
        raise RuntimeError(
            "TEST_DATABASE_DSN is not set. Run docker-compose.test.yml or set env var."
        )
    return dsn
