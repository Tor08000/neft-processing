#!/usr/bin/env sh
set -e

echo "[entrypoint] core-api starting"

# Start API (migrations can be added back when Alembic config is ready)
echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
