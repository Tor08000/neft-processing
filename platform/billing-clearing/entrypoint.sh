#!/usr/bin/env sh
set -e

ROLE="${ROLE:-worker}"  # worker or beat
QUEUES="${QUEUES:-celery,default,billing,pdf}"

echo "[entrypoint] starting celery role=${ROLE}"

if python -c "import app; print(f'[entrypoint] app import ok: {app.__file__}')"; then
  :
else
  echo "[entrypoint] failed to import app"
  python -c "import sys; print(f'[entrypoint] sys.path: {sys.path}')"
  exit 1
fi

if [ "$ROLE" = "beat" ]; then
  exec python -m celery \
    -A app.celery_app:celery_app \
    beat \
    --loglevel=INFO
else
  exec python -m celery \
    -A app.celery_app:celery_app \
    worker \
    --loglevel=INFO \
    -Q "${QUEUES}"
fi
