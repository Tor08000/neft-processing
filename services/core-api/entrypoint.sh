#!/usr/bin/env sh
set -e

echo "[entrypoint] core-api starting"

# Ensure shared python package is importable even if PYTHONPATH was not
# propagated for some reason (e.g. overridden by docker-compose env).
export PYTHONPATH="/opt/python:/app:${PYTHONPATH}"

# Start API (migrations can be added back when Alembic config is ready)
echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
