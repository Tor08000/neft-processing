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
schema = os.getenv("DB_SCHEMA", "public")

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
echo "[entrypoint] waiting for redis..."
wait_for_redis

# Run migrations before starting the API to guarantee schema availability
ALEMBIC_CONFIG=${ALEMBIC_CONFIG:-app/alembic.ini}
MIGRATIONS_RETRIES=${MIGRATIONS_RETRIES:-5}
MIGRATIONS_RETRY_DELAY=${MIGRATIONS_RETRY_DELAY:-2}

echo "[entrypoint] applying migrations via alembic ($ALEMBIC_CONFIG)"

python - <<'PY'
import sys

from app.diagnostics.db_state import collect_inventory

try:
    inventory = collect_inventory()
except Exception as exc:  # noqa: BLE001 - startup diagnostics
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
    if alembic -c "$ALEMBIC_CONFIG" upgrade heads; then
        echo "[entrypoint] migrations applied"
        break
    fi

    if [ "$attempt" -eq "$MIGRATIONS_RETRIES" ]; then
        echo "[entrypoint] migrations failed after $attempt attempts; exiting" >&2
        exit 1
    fi

    echo "[entrypoint] migration attempt $attempt failed, retrying in $MIGRATIONS_RETRY_DELAY s"
    attempt=$((attempt + 1))
    sleep "$MIGRATIONS_RETRY_DELAY"
done

python - <<'PY'
import sys

from app.api.dependencies.schema_guard import REQUIRED_CORE_TABLES
from app.diagnostics.db_state import collect_inventory

try:
    inventory = collect_inventory()
except Exception as exc:  # noqa: BLE001 - startup diagnostics
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

if inventory.alembic_versions:
    print(f"[entrypoint] alembic versions present: {inventory.alembic_versions}", flush=True)
else:
    print("[entrypoint] alembic_version missing", flush=True)

missing = inventory.missing_tables(REQUIRED_CORE_TABLES)
print(f"[entrypoint] missing_required_tables={missing}", flush=True)
if missing:
    sys.exit(1)

print("[entrypoint] core tables present after migrations")
PY

echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
