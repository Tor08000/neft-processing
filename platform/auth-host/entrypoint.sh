#!/usr/bin/env bash
set -e

# На всякий случай ещё раз прописываем PYTHONPATH
export PYTHONPATH="/opt/python:${PYTHONPATH}"

echo "[entrypoint] auth-host starting"
if [ ! -f "/app/alembic.ini" ]; then
    echo "[entrypoint] missing alembic config: /app/alembic.ini" >&2
    exit 1
fi
echo "[entrypoint] auth-host running migrations"
alembic -c /app/alembic.ini upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
