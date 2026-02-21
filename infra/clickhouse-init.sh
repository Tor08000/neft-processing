#!/usr/bin/env bash
set -u

SQL_FILE="/docker-entrypoint-initdb.d/geo_analytics_variant3.sql"
APP_ENV="${APP_ENV:-dev}"
CLICKHOUSE_HOST="${CLICKHOUSE_HOST:-clickhouse}"
CLICKHOUSE_PORT="${CLICKHOUSE_PORT:-9000}"

if [[ ! -f "$SQL_FILE" ]]; then
  echo "[clickhouse-init] WARNING: SQL file not found: $SQL_FILE"
  exit 0
fi

echo "[clickhouse-init] Applying $SQL_FILE on ${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}"
if ! clickhouse-client --host "$CLICKHOUSE_HOST" --port "$CLICKHOUSE_PORT" --multiquery --queries-file "$SQL_FILE"; then
  if [[ "$APP_ENV" == "dev" || "$APP_ENV" == "local" ]]; then
    echo "[clickhouse-init] WARNING: init SQL failed in ${APP_ENV}; continuing startup"
    exit 0
  fi
  echo "[clickhouse-init] ERROR: init SQL failed in ${APP_ENV}"
  exit 1
fi

echo "[clickhouse-init] Init SQL applied successfully"
