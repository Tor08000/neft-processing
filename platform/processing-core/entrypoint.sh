#!/usr/bin/env sh
set -e

echo "[entrypoint] core-api starting"

export PYTHONPATH="/opt/python:/app:${PYTHONPATH}"

DB_SCHEMA=$(python - <<'PY'
import os
from app.db.schema import resolve_db_schema

resolution = resolve_db_schema()
db_url = os.getenv("DATABASE_URL")
print(resolution.schema)
if not db_url:
    raise SystemExit("[entrypoint] DATABASE_URL is not set")
PY
)
echo "[entrypoint] schema_resolved=${DB_SCHEMA}"

wait_for_postgres() {
    python - <<'PY'
import os
import sys
import time

from sqlalchemy.engine import make_url
import psycopg

dsn = os.getenv("DATABASE_URL")
schema = os.getenv("NEFT_DB_SCHEMA", "public").strip() or "public"
timeout = int(os.getenv("DB_WAIT_TIMEOUT", "60"))
interval = int(os.getenv("DB_WAIT_INTERVAL", "2"))

if not dsn:
    print("[entrypoint] DATABASE_URL is not set", file=sys.stderr, flush=True)
    sys.exit(1)

def _normalize_postgres_dsn(raw: str) -> str:
    if "postgresql" not in raw or "://" not in raw:
        return raw

    try:
        url = make_url(raw)
    except Exception:
        return raw

    if not url.drivername.startswith("postgresql"):
        return raw

    safe_url = url.set(drivername="postgresql")
    return safe_url.render_as_string(hide_password=False)

dsn = _normalize_postgres_dsn(dsn)
connect_kwargs = {"connect_timeout": 5, "prepare_threshold": 0, "options": f"-c search_path={schema}"}
deadline = time.time() + timeout
last_error = None

while time.time() < deadline:
    try:
        with psycopg.connect(dsn, **connect_kwargs) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001 - entrypoint diagnostics
        last_error = exc
        time.sleep(interval)

print(f"[entrypoint] postgres is not ready after {timeout}s: {last_error}", file=sys.stderr, flush=True)
sys.exit(1)
PY
}

echo "[entrypoint] waiting for postgres..."
wait_for_postgres

ALEMBIC_CONFIG=${ALEMBIC_CONFIG:-app/alembic.ini}
echo "[entrypoint] applying migrations via alembic ($ALEMBIC_CONFIG)"
alembic -c "$ALEMBIC_CONFIG" upgrade head

python - <<'PY'
from app.db import reset_engine

reset_engine()
print("[entrypoint] engine cache reset", flush=True)
PY

python - <<'PY'
import os
import sys

import psycopg
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

from app.db.schema import resolve_db_schema

resolution = resolve_db_schema()
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("[entrypoint] DATABASE_URL is not set for post-migration verification", file=sys.stderr, flush=True)
    sys.exit(1)

cfg = Config(os.getenv("ALEMBIC_CONFIG", "app/alembic.ini"))
cfg.set_main_option("sqlalchemy.url", db_url)
head_revision = ScriptDirectory.from_config(cfg).get_current_head()

url = make_url(db_url)
if url.drivername.endswith("+psycopg"):
    url = url.set(drivername="postgresql")
dsn = url.render_as_string(hide_password=False)

def _quote_schema(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'

connect_kwargs = {
    "prepare_threshold": 0,
    "options": f"-c search_path={resolution.schema}",
}

with psycopg.connect(dsn, **connect_kwargs) as conn:
    with conn.cursor() as cur:
        qualified_ops = f"{_quote_schema(resolution.schema)}.operations"
        qualified_version = f"{_quote_schema(resolution.schema)}.alembic_version"

        cur.execute("select to_regclass(%s)", (qualified_ops,))
        operations_reg = cur.fetchone()[0]
        cur.execute("select to_regclass(%s)", (qualified_version,))
        version_reg = cur.fetchone()[0]
        versions = []
        if version_reg is not None:
            cur.execute(f"select version_num from {qualified_version}")
            versions = [row[0] for row in cur.fetchall()]

if operations_reg is None or version_reg is None:
    print(
        f"[entrypoint] required tables missing after migrations: operations={operations_reg} alembic_version={version_reg}",
        file=sys.stderr,
        flush=True,
    )
    sys.exit(1)

unique_versions = set(versions)
if unique_versions != {head_revision}:
    print(
        f"[entrypoint] alembic_version mismatch: expected {{{head_revision}}}, found {sorted(unique_versions)}",
        file=sys.stderr,
        flush=True,
    )
    sys.exit(1)

print(
    f"[entrypoint] migration check passed: alembic_version={version_reg} operations={operations_reg} head={head_revision}",
    flush=True,
)
PY

if [ "${ENTRYPOINT_SKIP_APP}" = "1" ]; then
    echo "[entrypoint] ENTRYPOINT_SKIP_APP=1 is set; exiting after migrations"
    exit 0
fi

echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
