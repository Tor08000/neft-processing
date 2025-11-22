"""
Celery-приложение для NEFT workers.

Точка входа для команды:
    python -m celery -A services.workers.app.celery_app:celery_app worker -Q default,limits,antifraud,reports
"""

from __future__ import annotations

import os

from celery import Celery

from neft_shared.logging_setup import init_logging, get_logger

SERVICE_NAME = os.getenv("SERVICE_NAME", "workers")

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_URL = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

# Инициализируем логирование как можно раньше
init_logging(service_name=SERVICE_NAME)

logger = get_logger(__name__, service=SERVICE_NAME)

celery_app = Celery(
    "neft-workers",
    broker=BROKER_URL,
    backend=RESULT_URL,
)

# Базовая конфигурация Celery
celery_app.conf.update(
    task_default_queue="default",
    broker_connection_retry_on_startup=True,
    timezone=os.getenv("CELERY_TIMEZONE", "Europe/Moscow"),
    enable_utc=True,
)

# Автоматический поиск задач в пакете services.workers.*
# (tasks должны лежать, например, в services/workers/tasks/*.py)
celery_app.autodiscover_tasks(["services.workers"])


@celery_app.task(name="workers.ping")
def ping(x: int = 1) -> dict:
    """
    Простой ping-task, чтобы можно было проверить работу очереди:
        celery -A services.workers.app.celery_app:celery_app call workers.ping --args='[5]'
    """
    logger.info("Ping task executed", extra={"extra": {"x": x}})
    return {"pong": x}
