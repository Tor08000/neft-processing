#!/usr/bin/env sh
set -e

echo "[entrypoint] core-api starting"

# Ensure shared python package is importable even if PYTHONPATH was not
# propagated for some reason (e.g. overridden by docker-compose env).
export PYTHONPATH="/opt/python:/app:${PYTHONPATH}"

# Normalize DATABASE_URL to force the psycopg (v3) driver so SQLAlchemy
# does not try to import psycopg2 when the incoming URL omits a driver or
# explicitly requests psycopg2.
if [ -n "$DATABASE_URL" ]; then
  DATABASE_URL=$(python - <<'PY'
import os
from sqlalchemy.engine.url import make_url

raw = os.environ["DATABASE_URL"]
url = make_url(raw)
if url.drivername in {"postgres", "postgresql"} or url.drivername.endswith("+psycopg2"):
    url = url.set(drivername="postgresql+psycopg")
print(url)
PY
)
  export DATABASE_URL
  echo "[entrypoint] normalized DATABASE_URL=${DATABASE_URL}"
fi

# Start API (migrations can be added back when Alembic config is ready)
echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
