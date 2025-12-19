from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, Optional

DEFAULT_GATEWAY = "http://localhost"
DEFAULT_TIMEOUT = float(os.getenv("SMOKE_HTTP_TIMEOUT", "5"))
DEFAULT_RETRIES = int(os.getenv("SMOKE_HTTP_RETRIES", "3"))
DEFAULT_SLEEP = float(os.getenv("SMOKE_HTTP_RETRY_DELAY", "1"))
DEFAULT_SCHEMA = "public"


def gateway_base() -> str:
    return os.getenv("GATEWAY_BASE_URL", DEFAULT_GATEWAY).rstrip("/")


def build_url(path: str) -> str:
    base = gateway_base()
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def http_get(
    path: str,
    *,
    expect_json: bool = False,
    headers: Optional[Dict[str, str]] = None,
    retries: int = DEFAULT_RETRIES,
    timeout: float = DEFAULT_TIMEOUT,
) -> urllib.response.addinfourl:
    url = build_url(path)
    last_error: Optional[Exception] = None
    request = urllib.request.Request(url, headers=headers or {})

    for attempt in range(1, retries + 1):
        try:
            response = urllib.request.urlopen(request, timeout=timeout)  # nosec: B310 - smoke test helper
            if expect_json:
                content_type = response.headers.get("Content-Type", "")
                if "json" not in content_type:
                    raise AssertionError(f"Expected JSON Content-Type, got {content_type!r} for {url}")
            return response
        except (urllib.error.URLError, AssertionError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(DEFAULT_SLEEP)
    raise AssertionError(f"GET {url} failed after {retries} attempts: {last_error}")


def read_json(response: urllib.response.addinfourl) -> Any:
    payload = response.read()
    return json.loads(payload.decode())


def target_schema() -> str:
    return (os.getenv("NEFT_DB_SCHEMA") or DEFAULT_SCHEMA).strip() or DEFAULT_SCHEMA


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def schema_connect_kwargs(schema: str | None = None) -> Dict[str, str]:
    resolved = target_schema() if schema is None else schema
    return {"options": f"-c search_path={_quote_ident(resolved)}"}


def qualified_regclass(name: str, schema: str | None = None) -> str:
    resolved = target_schema() if schema is None else schema
    return f"{_quote_ident(resolved)}.{_quote_ident(name)}"


def normalize_pg_dsn(raw_dsn: str) -> str:
    if raw_dsn.startswith("postgresql+psycopg://"):
        return raw_dsn.replace("postgresql+psycopg://", "postgresql://", 1)
    if raw_dsn.startswith("postgresql+asyncpg://"):
        return raw_dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    return raw_dsn


def build_pg_dsn() -> str:
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return normalize_pg_dsn(dsn)

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "neft")
    password = os.getenv("POSTGRES_PASSWORD", "neft")
    db = os.getenv("POSTGRES_DB", "neft")

    return f"postgresql://{urllib.parse.quote(user)}:{urllib.parse.quote(password)}@{host}:{port}/{db}"


def assert_tables_exist(conn, table_names: Iterable[str], schema: str | None = None) -> None:
    names = list(table_names)
    resolved_schema = target_schema() if schema is None else schema
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_name = ANY(%s)
            """,
            (resolved_schema, names),
        )
        existing = {row[0] for row in cur.fetchall()}

    missing = set(table_names) - existing
    if missing:
        raise AssertionError(f"Missing tables: {', '.join(sorted(missing))}")
