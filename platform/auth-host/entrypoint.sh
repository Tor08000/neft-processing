#!/usr/bin/env bash
set -e

# На всякий случай ещё раз прописываем PYTHONPATH
export PYTHONPATH="/opt/python:${PYTHONPATH}"

echo "[entrypoint] auth-host starting"
if [ ! -f "/app/alembic.ini" ]; then
    echo "[entrypoint] missing alembic config: /app/alembic.ini" >&2
    exit 1
fi

POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-neft}"
POSTGRES_USER="${POSTGRES_USER:-neft}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-neft}"
RUNTIME_DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
if [ -n "${DATABASE_URL:-}" ] && [ "${DATABASE_URL}" != "${RUNTIME_DATABASE_URL}" ]; then
    echo "[entrypoint] warning: DATABASE_URL differs from runtime settings; forcing runtime DATABASE_URL for migrations"
fi
export DATABASE_URL="${RUNTIME_DATABASE_URL}"

python - <<'PY'
import os
import re
import urllib.parse

import psycopg

dsn = os.environ["DATABASE_URL"]


def _mask(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
        if parsed.username or parsed.password:
            netloc = parsed.hostname or ""
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            if parsed.username:
                netloc = f"{parsed.username}:***@{netloc}"
            return urllib.parse.urlunsplit(
                (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
            )
    except Exception:
        pass
    return re.sub(r"//([^:@/]+):[^@/]+@", r"//\\1:***@", url)


print(f"[entrypoint] DATABASE_URL={_mask(dsn)}")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT current_user, current_database(), current_schema()")
        current_user, current_database, current_schema = cur.fetchone()
        print(
            "[entrypoint] db probe: user=%s db=%s schema=%s"
            % (current_user, current_database, current_schema)
        )
PY

echo "[entrypoint] auth-host running migrations"
alembic -c /app/alembic.ini upgrade head

python - <<'PY'
import os
import sys

import psycopg

dsn = os.environ["DATABASE_URL"]
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'users'"
        )
        if cur.fetchone() is None:
            print("[entrypoint] migration did not create users", file=sys.stderr)
            sys.exit(1)
print("[entrypoint] migration check: public.users exists")
PY

echo "[entrypoint] auth-host bootstrap admin"
python - <<'PY'
import asyncio

from app.bootstrap import bootstrap_admin

asyncio.run(bootstrap_admin())
PY

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
