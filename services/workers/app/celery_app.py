"""
Celery-приложение для NEFT workers.

Точка входа для команды:
    python -m celery -A services.workers.app.celery_app:celery_app worker -Q default,limits,antifraud,reports
"""

from __future__ import annotations

from celery import Celery

from neft_shared.logging_setup import get_logger, init_logging

from .settings import settings

SERVICE_NAME = settings.service_name

# Инициализируем логирование как можно раньше
init_logging(service_name=SERVICE_NAME)

logger = get_logger(__name__)

celery_app = Celery(
    "neft-workers",
    broker=settings.broker_url,
    backend=settings.result_backend,
    include=["services.workers.app.tasks"],
)

# Базовая конфигурация Celery
celery_app.conf.update(
    task_default_queue=settings.task_default_queue,
    task_default_exchange=settings.task_default_queue,
    task_default_routing_key=settings.task_default_queue,
    broker_connection_retry_on_startup=True,
    timezone=settings.timezone,
    enable_utc=True,
    result_expires=settings.result_expires,
    task_default_retry_delay=settings.task_default_retry_delay,
    task_acks_late=True,
    task_max_retries=settings.task_max_retries,
    broker_transport_options={"visibility_timeout": settings.visibility_timeout},
    worker_max_tasks_per_child=settings.worker_max_tasks_per_child,
    worker_prefetch_multiplier=settings.worker_prefetch_multiplier,
    task_soft_time_limit=settings.task_soft_time_limit,
    task_time_limit=settings.task_time_limit,
)

# Автоматический поиск задач в пакете services.workers.app.tasks
celery_app.autodiscover_tasks(["services.workers.app.tasks"])
