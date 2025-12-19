#!/usr/bin/env sh
set -e

echo "[entrypoint] core-api starting"

export PYTHONPATH="/opt/python:/app:${PYTHONPATH}"

python - <<'PY'
import os
from sqlalchemy.engine.url import make_url
from app.db.schema import resolve_db_schema

resolution = resolve_db_schema()
db_url = os.getenv("DATABASE_URL")
print(f"[entrypoint] {resolution.line()}", flush=True)

if db_url:
    masked = make_url(db_url).render_as_string(hide_password=True)
    print(f"[entrypoint] DATABASE_URL={masked}", flush=True)
    print(f"[entrypoint] search_path={resolution.search_path}", flush=True)
else:
    print("[entrypoint] DATABASE_URL is not set", flush=True)
PY

wait_for_postgres() {
    python - <<'PY'
import os
import sys
import time

from sqlalchemy.engine import make_url
import psycopg

dsn = os.getenv("DATABASE_URL")
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
deadline = time.time() + timeout
last_error = None

while time.time() < deadline:
    try:
        with psycopg.connect(dsn, connect_timeout=5, prepare_threshold=0) as conn:
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
import os
import sys

from sqlalchemy import text

from app.db import make_engine, reset_engine
from app.db.schema import resolve_db_schema

resolution = resolve_db_schema()
db_url = os.getenv("DATABASE_URL")

if not db_url:
    print("[entrypoint] DATABASE_URL is not set for post-migration verification", file=sys.stderr, flush=True)
    sys.exit(1)

engine = make_engine(
    db_url,
    schema=resolution.target_schema,
)

with engine.connect() as connection:
    operations_reg = connection.execute(
        text("select to_regclass(:regclass)"),
        {"regclass": f"{resolution.target_schema}.operations"},
    ).scalar_one_or_none()
    version_reg = connection.execute(
        text("select to_regclass(:regclass)"),
        {"regclass": f"{resolution.target_schema}.alembic_version"},
    ).scalar_one_or_none()
    table_count = connection.execute(
        text(
            """
            select count(*)
            from information_schema.tables
            where table_schema = :schema
            """
        ),
        {"schema": resolution.target_schema},
    ).scalar_one()

if operations_reg is None or version_reg is None:
    print(
        f"[entrypoint] required tables missing after migrations: operations={operations_reg} alembic_version={version_reg}",
        file=sys.stderr,
        flush=True,
    )
    sys.exit(1)

print(
    f"[entrypoint] migration check: alembic_version={version_reg} operations={operations_reg} table_count={table_count}",
    flush=True,
)

reset_engine()
print("[entrypoint] ORM engine cache reset after migrations", flush=True)
PY

if [ "${ENTRYPOINT_SKIP_APP}" = "1" ]; then
    echo "[entrypoint] ENTRYPOINT_SKIP_APP=1 is set; exiting after migrations"
    exit 0
fi

echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
