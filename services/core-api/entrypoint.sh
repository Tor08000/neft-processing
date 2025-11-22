#!/usr/bin/env sh
set -e

echo "[entrypoint] core-api starting"

# Ensure shared python package is importable even if PYTHONPATH was not
# propagated for some reason (e.g. overridden by docker-compose env).
export PYTHONPATH="/opt/python:/app:${PYTHONPATH}"

# Normalize Postgres URLs to force the psycopg (v3) driver so SQLAlchemy does not
# try to import psycopg2 when the incoming URL omits a driver or explicitly
# requests psycopg2. Apply to both DATABASE_URL and NEFT_DB_URL when present.
normalize_url() {
  VAR_NAME=$1
  CURRENT_VALUE=$(eval echo "\$$VAR_NAME")

  if [ -n "$CURRENT_VALUE" ]; then
    NEW_VALUE=$(python - <<'PY'
import os
import sys
from sqlalchemy.engine.url import make_url

var_name = sys.argv[1]
raw = os.environ[var_name]
url = make_url(raw)
if url.drivername in {"postgres", "postgresql"} or url.drivername.endswith("+psycopg2"):
    url = url.set(drivername="postgresql+psycopg")
print(url.render_as_string(hide_password=False))
PY
"$VAR_NAME")

    export "$VAR_NAME"="$NEW_VALUE"
    echo "[entrypoint] normalized ${VAR_NAME}=${NEW_VALUE}"
  fi
}

normalize_url DATABASE_URL
normalize_url NEFT_DB_URL

# Guarantee the Postgres driver is available even if the image was built
# without it (e.g., when an old cached image is reused without a rebuild).
python - <<'PY'
import importlib
import subprocess
import sys

try:
    importlib.import_module("psycopg2")
except ImportError:
    print("[entrypoint] psycopg2 missing; installing psycopg2-binary...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "psycopg2-binary"],
        check=True,
    )
PY

# Start API (migrations can be added back when Alembic config is ready)
echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
