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

bootstrap_enabled="${NEFT_BOOTSTRAP_ENABLED:-1}"
bootstrap_enabled="$(echo "${bootstrap_enabled}" | tr '[:upper:]' '[:lower:]')"
if [ "${bootstrap_enabled}" != "0" ] && [ "${bootstrap_enabled}" != "false" ] \
    && [ "${bootstrap_enabled}" != "no" ] && [ "${bootstrap_enabled}" != "off" ]; then
    required_envs=(
        NEFT_BOOTSTRAP_ADMIN_PASSWORD
        NEFT_BOOTSTRAP_CLIENT_PASSWORD
        NEFT_BOOTSTRAP_PARTNER_PASSWORD
    )
    for env_name in "${required_envs[@]}"; do
        if [ -z "${!env_name:-}" ]; then
            echo "[entrypoint] missing required env: ${env_name}" >&2
            exit 1
        fi
    done
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

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
