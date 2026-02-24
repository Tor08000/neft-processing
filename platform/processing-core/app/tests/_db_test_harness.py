from __future__ import annotations

import os


def get_test_dsn_or_fail() -> str:
    dsn = (os.getenv("TEST_DATABASE_DSN") or "").strip()
    if not dsn:
        dsn = (os.getenv("DATABASE_URL_TEST") or "").strip()
    if not dsn:
        dsn = (os.getenv("DATABASE_URL") or "").strip()
    if not dsn:
        raise RuntimeError(
            "Database DSN is not set. Provide TEST_DATABASE_DSN (preferred) or DATABASE_URL_TEST or DATABASE_URL."
        )
    return dsn
