import os
from typing import Optional

import os

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from app.db import engine as app_engine


def get_database_url() -> str:
    """Resolve a usable database URL for tests.

    Prefers the DATABASE_URL environment variable and falls back to the
    application engine URL, which defaults to the docker-compose Postgres
    service when unset.
    """

    env_url: Optional[str] = os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    return app_engine.url.render_as_string(hide_password=False)


def ensure_connectable(db_url: str) -> Engine:
    """Create an engine for the provided URL and ensure it is reachable."""

    engine_kwargs = {}
    if db_url.startswith("postgresql"):
        engine_kwargs["connect_args"] = {"prepare_threshold": 0}

    connectable = sa.create_engine(db_url, **engine_kwargs)
    try:
        with connectable.connect() as connection:
            connection.exec_driver_sql("select 1")
    except sa.exc.OperationalError as exc:  # pragma: no cover - diagnostic skip
        pytest.skip(f"Postgres is not available: {exc}")

    return connectable
