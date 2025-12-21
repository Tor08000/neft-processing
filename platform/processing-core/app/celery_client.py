# services/core-api/app/celery_client.py
from __future__ import annotations

import os
from celery import Celery

# Берём те же env, что и воркеры (у тебя уже есть в .env / docker-compose)
BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_URL = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
DEFAULT_QUEUE = os.getenv("CELERY_DEFAULT_QUEUE", "celery")

TIMEZONE = os.getenv("CELERY_TIMEZONE", "Europe/Moscow")
ENABLE_UTC = os.getenv("CELERY_ENABLE_UTC", "True").lower() == "true"

celery_client = Celery(
    "neft-core-api",
    broker=BROKER_URL,
    backend=RESULT_URL,
)

celery_client.conf.update(
    broker_connection_retry_on_startup=True,
    timezone=TIMEZONE,
    enable_utc=ENABLE_UTC,
    task_default_queue=DEFAULT_QUEUE,
    task_default_exchange=DEFAULT_QUEUE,
    task_default_routing_key=DEFAULT_QUEUE,
)

# Register billing tasks
try:  # pragma: no cover - optional celery runtime
    import app.tasks.billing_pdf  # noqa: F401
except Exception:
    pass
