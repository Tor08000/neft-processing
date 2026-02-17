#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:=postgresql://postgres:postgres@127.0.0.1:5432/neft}"

python -m pip install --upgrade pip setuptools wheel
python -m pip install alembic psycopg[binary] sqlalchemy
python -m pip install -e shared/python
python -m pip install -r platform/auth-host/requirements.txt
python -m pip install -r platform/processing-core/requirements.txt

check_single_head() {
  local config_path="$1"
  local workdir="$2"
  local service_name="$3"

  echo "==> Checking alembic heads for ${service_name}"
  local heads
  heads=$(cd "$workdir" && alembic -c "$config_path" heads)
  local count
  count=$(printf '%s\n' "$heads" | sed '/^\s*$/d' | wc -l | tr -d ' ')
  if [[ "$count" -ne 1 ]]; then
    echo "Expected exactly 1 alembic head for ${service_name}, got ${count}"
    printf '%s\n' "$heads"
    exit 1
  fi
}

export DATABASE_URL
export AUTH_DB_DSN="$DATABASE_URL"
export AUTH_DB_SCHEMA="public"
export NEFT_DB_SCHEMA="processing_core"

check_single_head "alembic.ini" "platform/auth-host" "auth-host"
(cd platform/auth-host && alembic -c alembic.ini upgrade head)
(cd platform/auth-host && alembic -c alembic.ini upgrade head)

check_single_head "app/alembic.ini" "platform/processing-core" "processing-core"
(cd platform/processing-core && alembic -c app/alembic.ini upgrade head)
(cd platform/processing-core && alembic -c app/alembic.ini upgrade head)
