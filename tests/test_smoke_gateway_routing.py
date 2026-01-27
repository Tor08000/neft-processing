from __future__ import annotations

import os
from typing import Any

import psycopg
import pytest
import requests


DEFAULT_GATEWAY = "http://127.0.0.1"
DEFAULT_DB = "postgresql+psycopg://neft:neft@127.0.0.1:5432/neft"


def _build_url(path: str) -> str:
    base = os.getenv("GATEWAY_BASE_URL", DEFAULT_GATEWAY).rstrip("/")
    normalized = path if path.startswith("/") else f"/{path}"
    return f"{base}{normalized}"


def _assert_health(path: str) -> None:
    response = requests.get(_build_url(path), timeout=5)
    assert response.status_code == 200

    payload: Any
    if "application/json" in response.headers.get("Content-Type", ""):
        payload = response.json()
        assert payload.get("status") == "ok"
    else:
        assert "OK" in response.text


def _build_db_url() -> str | None:
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    return DEFAULT_DB


@pytest.mark.smoke
def test_gateway_health_endpoints() -> None:
    _assert_health("/health")
    _assert_health("/api/core/health")
    _assert_health("/api/v1/auth/health")
    _assert_health("/api/ai/api/v1/health")


@pytest.mark.smoke
def test_database_sanity() -> None:
    db_url = _build_db_url()
    if not db_url:
        pytest.skip("DATABASE_URL not provided")

    dsn = db_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.alembic_version')")
        assert cur.fetchone()[0] is not None, "alembic_version table missing"

        cur.execute("SELECT to_regclass('public.operations')")
        assert cur.fetchone()[0] is not None, "operations table missing"
