#!/usr/bin/env sh
set -e

echo "[entrypoint] core-api starting"

# Если потом будем подключать alembic — вернём миграции сюда.
# Сейчас, чтобы не мучиться с alembic.ini, просто стартуем API.

echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
