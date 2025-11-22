from __future__ import annotations

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
    name="ping",
)
def ping(self, x: int = 1) -> dict:
    """
    Базовая тестовая задача для проверки очереди Celery.
    Вызывается через HTTP-эндпоинт /api/v1/health/enqueue.
    """
    return {"pong": x}


@shared_task(name="periodic.ping")
def periodic_ping() -> dict:
    """
    Периодическая задача для beat — просто пишет лог раз в N секунд.
    """
    logger.info("Periodic ping OK")
    return {"ok": True}


# ВАЖНО:
# Импортируем подмодуль limits, чтобы Celery увидел задачи лимитов.
from . import limits  # noqa: F401
