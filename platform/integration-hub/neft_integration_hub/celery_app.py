from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from neft_integration_hub.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "integration-hub",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    timezone=settings.celery_timezone,
    enable_utc=settings.celery_enable_utc,
    task_default_queue=settings.celery_default_queue,
    task_default_exchange=settings.celery_default_queue,
    task_default_routing_key=settings.celery_default_queue,
    beat_schedule={
        "edo.poll": {
            "task": "edo.poll",
            "schedule": crontab(minute="*/1"),
        },
        "webhook.retry": {
            "task": "webhook.retry",
            "schedule": crontab(minute="*/1"),
        },
    },
)

try:  # pragma: no cover
    import neft_integration_hub.tasks  # noqa: F401
except Exception:
    pass


__all__ = ["celery_app"]
