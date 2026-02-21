#!/usr/bin/env bash
set -e

# На всякий случай ещё раз прописываем PYTHONPATH
export PYTHONPATH="/app:/opt/python:${PYTHONPATH}"

echo "[entrypoint] auth-host starting"
if [ ! -f "/app/alembic.ini" ]; then
    echo "[entrypoint] missing alembic config: /app/alembic.ini" >&2
    exit 1
fi

AUTH_PRIVATE_KEY_PATH="${AUTH_PRIVATE_KEY_PATH:-/data/keys/private.pem}"
AUTH_PUBLIC_KEY_PATH="${AUTH_PUBLIC_KEY_PATH:-/data/keys/public.pem}"
export AUTH_PRIVATE_KEY_PATH
export AUTH_PUBLIC_KEY_PATH

export DEV_SEED_USERS="${DEV_SEED_USERS:-1}"

APP_ENV_NORMALIZED="$(printf '%s' "${APP_ENV:-}" | tr '[:upper:]' '[:lower:]')"
START_MODE_NORMALIZED="$(printf '%s' "${START_MODE:-}" | tr '[:upper:]' '[:lower:]')"

RUN_MODE="strict"
if [ "${APP_ENV_NORMALIZED}" = "prod" ]; then
    RUN_MODE="prod"
elif [ "${APP_ENV_NORMALIZED}" = "dev" ] || [ "${START_MODE_NORMALIZED}" = "dev" ]; then
    RUN_MODE="dev"
fi

echo "[entrypoint] run mode: ${RUN_MODE} (APP_ENV=${APP_ENV:-<unset>} START_MODE=${START_MODE:-<unset>})"

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
ALEMBIC_OPTS="${ALEMBIC_OPTS:-}"
ALEMBIC_OPTS="${ALEMBIC_OPTS//-q/}"
mapfile -t alembic_heads < <(alembic ${ALEMBIC_OPTS} -c /app/alembic.ini heads)
if [ "${#alembic_heads[@]}" -gt 1 ]; then
    echo "[entrypoint] error: multiple alembic heads detected in auth-host:" >&2
    printf '[entrypoint]   %s\n' "${alembic_heads[@]}" >&2
    echo "[entrypoint] resolve by running: alembic merge -m \"merge heads\" <head1> <head2>" >&2
    exit 1
fi
alembic ${ALEMBIC_OPTS} -c /app/alembic.ini upgrade head

if python - <<'PY'
import os
import sys
import asyncio

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

if os.getenv("DEV_SEED_USERS", "0") == "1":
    from app.seeds.demo_users import ensure_user, get_demo_users

    async def _seed() -> None:
        for demo_user in get_demo_users():
            await ensure_user(
                demo_user,
                force_password=True,
                sync_roles=True,
            )

    asyncio.run(_seed())
    print("[entrypoint] DEV users ready")
PY
then
    :
else
    if [ "${RUN_MODE}" = "dev" ]; then
        echo "[entrypoint] WARNING: users check/seed failed in dev, continuing startup"
    else
        echo "[entrypoint] ERROR: users check/seed failed" >&2
        exit 1
    fi
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
