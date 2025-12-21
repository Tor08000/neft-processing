#!/usr/bin/env sh
set -e

ROLE="${ROLE:-worker}"  # worker or beat
QUEUES="${QUEUES:-celery,default,billing,pdf}"

echo "[entrypoint] starting celery role=${ROLE}"

if [ "$ROLE" = "beat" ]; then
  exec python -m celery \
    -A services.workers.app.celery_app:celery_app \
    beat \
    --loglevel=INFO
else
  exec python -m celery \
    -A services.workers.app.celery_app:celery_app \
    worker \
    --loglevel=INFO \
    -Q "${QUEUES}"
fi
