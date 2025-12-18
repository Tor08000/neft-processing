#!/usr/bin/env sh
set -e

echo "[entrypoint] core-api starting"

# Ensure shared python package is importable even if PYTHONPATH was not
# propagated for some reason (e.g. overridden by docker-compose env).
export PYTHONPATH="/opt/python:/app:${PYTHONPATH}"

python - <<'PY'
import os
from sqlalchemy.engine.url import make_url

db_url = os.getenv("DATABASE_URL")
schema = os.getenv("DB_SCHEMA") or os.getenv("NEFT_DB_SCHEMA") or "public"

if not db_url:
    print("[entrypoint] DATABASE_URL is not set", flush=True)
else:
    masked = make_url(db_url).render_as_string(hide_password=True)
    search_path = f"{schema},public" if schema else "public"
    print(f"[entrypoint] DATABASE_URL={masked}", flush=True)
    print(f"[entrypoint] DB_SCHEMA={schema} search_path={search_path}", flush=True)
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

deadline = time.time() + timeout
last_error = None


def _normalize_postgres_dsn(raw: str) -> str:
    """Convert SQLAlchemy-style URLs to psycopg-friendly DSNs.

    psycopg accepts plain libpq connection strings and "postgresql://" URLs, but
    will reject dialect suffixes like ``postgresql+psycopg://``. To support both
    DSN styles used by the project we normalise URLs with a scheme by stripping
    driver aliases and rendering them without hiding the password.
    """

    if "postgresql" not in raw:
        return raw

    if "://" not in raw:
        return raw

    try:
        url = make_url(raw)
    except Exception:
        return raw

    if not url.drivername.startswith("postgresql"):
        return raw

    safe_url = url.set(drivername="postgresql")
    return safe_url.render_as_string(hide_password=False)


if not dsn:
    print("[entrypoint] DATABASE_URL is not set", file=sys.stderr)
    sys.exit(1)

dsn = _normalize_postgres_dsn(dsn)

while time.time() < deadline:
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001 - entrypoint diagnostics
        last_error = exc
        time.sleep(interval)

print(f"[entrypoint] postgres is not ready after {timeout}s: {last_error}", file=sys.stderr)
sys.exit(1)
PY
}

wait_for_redis() {
    python - <<'PY'
import os
import sys
import time

import redis

url = os.getenv("REDIS_URL")
timeout = int(os.getenv("REDIS_WAIT_TIMEOUT", "60"))
interval = int(os.getenv("REDIS_WAIT_INTERVAL", "2"))

deadline = time.time() + timeout
last_error = None
client = redis.Redis.from_url(url)

while time.time() < deadline:
    try:
        client.ping()
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001 - entrypoint diagnostics
        last_error = exc
        time.sleep(interval)

print(f"[entrypoint] redis is not ready after {timeout}s: {last_error}", file=sys.stderr)
sys.exit(1)
PY
}

echo "[entrypoint] waiting for postgres..."
wait_for_postgres
if [ "${SKIP_REDIS_WAIT}" != "1" ]; then
    echo "[entrypoint] waiting for redis..."
    wait_for_redis
fi

# Shared diagnostics helpers
dump_migration_diagnostics() {
    set +e
    echo "[entrypoint] alembic heads output:" >&2
    alembic -c "$ALEMBIC_CONFIG" heads
    echo "[entrypoint] alembic current output:" >&2
    alembic -c "$ALEMBIC_CONFIG" current
    echo "[entrypoint] table inventory (all schemas):" >&2
    python - <<'PY'
from app.diagnostics.db_state import collect_inventory

inventory = collect_inventory()
for schema, table in inventory.tables:
    print(f"{schema}.{table}")
PY
    set -e
}

verify_migration_ddls() {
    python - <<'PY'
import os
import sys

from sqlalchemy import create_engine, event, text

from app.diagnostics.db_state import to_regclass

schema = os.getenv("DB_SCHEMA") or os.getenv("NEFT_DB_SCHEMA") or "public"
url = os.getenv("DATABASE_URL")
required_tables = (
    "alembic_version",
    "operations",
    "accounts",
    "ledger_entries",
    "limit_configs",
)

if not url:
    print("[entrypoint] DATABASE_URL is not set for migration verification", file=sys.stderr)
    sys.exit(1)

debug_sql = os.getenv("DB_DEBUG_SQL") == "1"
engine_kwargs = {"future": True, "pool_pre_ping": True, "echo": debug_sql}
if url.startswith("postgresql"):
    engine_kwargs["connect_args"] = {"options": f"-csearch_path={schema},public"}

engine = create_engine(url, **engine_kwargs)

if debug_sql:
    def _log_event(conn, *_args, _name):
        print(
            f"[entrypoint] DB_DEBUG_SQL: {_name.upper()} connection={hex(id(conn))}",
            flush=True,
        )

    for name in ("begin", "commit", "rollback", "close"):
        event.listen(engine, name, lambda conn, *_args, _name=name: _log_event(conn, _name=_name))


def _collect_required_tables() -> dict[str, str | None]:
    with engine.connect() as conn:
        with conn.begin():
            return {name: to_regclass(conn, schema, name) for name in required_tables}


def _collect_inventory() -> tuple[list[str], list[str]]:
    with engine.connect() as conn:
        user_schemas = conn.execute(
            text(
                """
                select nspname
                from pg_namespace
                where nspname not in ('pg_catalog','information_schema','pg_toast')
                order by 1
                """
            )
        ).scalars().all()
        user_tables = [
            f"{row.table_schema}.{row.table_name}"
            for row in conn.execute(
                text(
                    """
                    select table_schema, table_name
                    from information_schema.tables
                    where table_schema not in ('pg_catalog','information_schema','pg_toast')
                    order by 1,2
                    """
                )
            )
        ]
    return user_schemas, user_tables


results = _collect_required_tables()
missing = [name for name, reg in results.items() if reg is None]
if missing:
    user_schemas, user_tables = _collect_inventory()
    print(
        f"[entrypoint] migration verification failed; missing tables in schema '{schema}': {missing}",
        file=sys.stderr,
    )
    print(f"[entrypoint] user schemas: {user_schemas}", file=sys.stderr)
    print(f"[entrypoint] user tables ({len(user_tables)}): {user_tables}", file=sys.stderr)
    print(
        "[entrypoint] hint: docker compose logs --tail=200 postgres to check if the DB was reset",
        file=sys.stderr,
    )
    sys.exit(1)

print(
    f"[entrypoint] verified required tables exist in schema '{schema}': {sorted(results)}",
    flush=True,
)
PY
}

after_commit_visibility_probe() {
    python - <<'PY'
import os
import sys

from sqlalchemy import create_engine, text

url = os.getenv("DATABASE_URL")
if not url:
    print("[entrypoint] DATABASE_URL is not set for after-commit probe", file=sys.stderr)
    sys.exit(1)

engine = create_engine(url, future=True, pool_pre_ping=True, echo=os.getenv("DB_DEBUG_SQL") == "1")

with engine.connect() as conn:
    operations_reg = conn.execute(text("select to_regclass('public.operations')")).scalar_one_or_none()
    public_table_count = conn.execute(
        text("select count(*) from information_schema.tables where table_schema='public'")
    ).scalar_one()

print(f"[entrypoint] after-commit probe: operations regclass in public = {operations_reg}", flush=True)
print(
    f"[entrypoint] after-commit probe: table count in public schema = {public_table_count}",
    flush=True,
)
PY
}

log_db_fingerprint() {
    python - <<'PY'
import os
import sys

from app.diagnostics.db_state import log_fingerprint_from_url

schema = os.getenv("DB_SCHEMA", "public") or "public"
url = os.getenv("DATABASE_URL")
label = os.getenv("DB_FINGERPRINT_LABEL", "")

if not url:
    print("[entrypoint] DATABASE_URL is not set for fingerprint collection", file=sys.stderr)
    sys.exit(1)


def _emit(message: str) -> None:
    print(f"[entrypoint] {message}", flush=True)


log_fingerprint_from_url(url=url, schema=schema, emitter=_emit, label=label)
PY
}

assert_alembic_state() {
    heads_output=$(alembic -c "$ALEMBIC_CONFIG" heads 2>&1)
    current_output=$(alembic -c "$ALEMBIC_CONFIG" current 2>&1)

    echo "[entrypoint] alembic heads:" >&2
    echo "$heads_output" >&2
    echo "[entrypoint] alembic current:" >&2
    echo "$current_output" >&2

    if [ -z "$current_output" ]; then
        echo "[entrypoint] alembic current returned empty output; migration failed" >&2
        exit 1
    fi
}

# Run migrations before starting the API to guarantee schema availability
ALEMBIC_CONFIG=${ALEMBIC_CONFIG:-app/alembic.ini}
MIGRATIONS_RETRIES=${MIGRATIONS_RETRIES:-5}
MIGRATIONS_RETRY_DELAY=${MIGRATIONS_RETRY_DELAY:-2}

echo "[entrypoint] applying migrations via alembic ($ALEMBIC_CONFIG)"

python - <<'PY'
import sys
import traceback

from app.diagnostics.db_state import collect_inventory

try:
    inventory = collect_inventory()
except Exception as exc:  # noqa: BLE001 - startup diagnostics
    traceback.print_exc()
    print(f"[entrypoint] failed to collect pre-migration inventory: {exc}", flush=True)
    sys.exit(1)

print(
    "[entrypoint] pre-migration target: "
    f"db={inventory.current_database} user={inventory.current_user} "
    f"server={inventory.server_addr}:{inventory.server_port} search_path={inventory.search_path}",
    flush=True,
)
print(f"[entrypoint] pre-migration schemas: {inventory.schemas}", flush=True)
print(
    f"[entrypoint] pre-migration tables sample: {[f'{s}.{t}' for s, t in inventory.tables[:30]]}",
    flush=True,
)
PY

attempt=1
while [ "$attempt" -le "$MIGRATIONS_RETRIES" ]; do
    DB_FINGERPRINT_LABEL="pre-migration-attempt-$attempt" log_db_fingerprint

    if alembic -c "$ALEMBIC_CONFIG" upgrade head; then
        assert_alembic_state
        after_commit_visibility_probe
        if verify_migration_ddls; then
            DB_FINGERPRINT_LABEL="post-migration-attempt-$attempt" log_db_fingerprint
            echo "[entrypoint] migrations applied"
            break
        fi

        echo "[entrypoint] migration attempt $attempt reported success but verification failed" >&2
        dump_migration_diagnostics
        exit 1
    fi

    if [ "$attempt" -eq "$MIGRATIONS_RETRIES" ]; then
        echo "[entrypoint] migrations failed after $attempt attempts; exiting" >&2
        exit 1
    fi

    echo "[entrypoint] migration attempt $attempt failed, retrying in $MIGRATIONS_RETRY_DELAY s"
    attempt=$((attempt + 1))
    sleep "$MIGRATIONS_RETRY_DELAY"
done

set +e
python - <<'PY'
import sys
import traceback

from app.api.dependencies.schema_guard import REQUIRED_CORE_TABLES
from app.diagnostics.db_state import collect_inventory

try:
    inventory = collect_inventory()
except Exception as exc:  # noqa: BLE001 - startup diagnostics
    traceback.print_exc()
    print(f"[entrypoint] diagnostics failed: {exc}", flush=True)
    sys.exit(1)

print(
    "[entrypoint] post-migration target: "
    f"db={inventory.current_database} user={inventory.current_user} "
    f"server={inventory.server_addr}:{inventory.server_port} search_path={inventory.search_path}",
    flush=True,
)
print(f"[entrypoint] post-migration schemas: {inventory.schemas}", flush=True)
print(
    f"[entrypoint] post-migration tables sample: {[f'{s}.{t}' for s, t in inventory.tables[:30]]}",
    flush=True,
)

missing_version = not inventory.alembic_versions
if inventory.alembic_versions:
    print(f"[entrypoint] alembic versions present: {inventory.alembic_versions}", flush=True)
else:
    print("[entrypoint] alembic_version missing", flush=True)

missing_tables = inventory.missing_tables(REQUIRED_CORE_TABLES)
print(f"[entrypoint] missing_required_tables={missing_tables}", flush=True)

if missing_version or missing_tables:
    sys.exit(2)

print("[entrypoint] core tables present after migrations")
PY
diagnostics_status=$?
set -e

if [ "$diagnostics_status" -ne 0 ]; then
    dump_migration_diagnostics
    exit 1
fi

python - <<'PY'
from app.db import reset_engine

reset_engine()
print("[entrypoint] ORM engine cache reset after migrations", flush=True)
PY

if [ "${ENTRYPOINT_SKIP_APP}" = "1" ]; then
    echo "[entrypoint] ENTRYPOINT_SKIP_APP=1 is set; exiting after migrations"
    exit 0
fi

echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
