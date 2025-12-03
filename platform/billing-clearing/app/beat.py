from .celery_app import celery_app
from .settings import settings


# Минимальный расписатель для демо-окружения
celery_app.conf.beat_schedule = {
    "periodic-ping": {
        "task": "periodic.ping",
        "schedule": 60.0,
    },
    "apply-daily-limits": {
        "task": "limits.apply_daily_limits",
        "schedule": 3600.0,
    },
}

celery_app.conf.timezone = settings.timezone

celery = celery_app

__all__ = ["celery"]
