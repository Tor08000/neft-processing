import json
import time
from datetime import timedelta
from typing import Any, Dict

from celery import Celery, signals
from kombu import Exchange, Queue

from .config import settings

# Celery app
celery = Celery("neft-workers", broker=settings.redis_url, backend=settings.redis_url)

# Общий exchange (direct)
exchange = Exchange(f"{settings.queue_prefix}:ex", type="direct")

# Очереди
q_limits    = Queue(f"{settings.queue_prefix}:limits",    exchange=exchange, routing_key="limits")
q_reports   = Queue(f"{settings.queue_prefix}:reports",   exchange=exchange, routing_key="reports")
q_backups   = Queue(f"{settings.queue_prefix}:backups",   exchange=exchange, routing_key="backups")
q_prices    = Queue(f"{settings.queue_prefix}:prices",    exchange=exchange, routing_key="prices")
q_antifraud = Queue(f"{settings.queue_prefix}:antifraud", exchange=exchange, routing_key="antifraud")

celery.conf.task_queues = [q_limits, q_reports, q_backups, q_prices, q_antifraud]

# Дефолтные настройки задач
celery.conf.update(
    task_default_queue=f"{settings.queue_prefix}:limits",
    task_default_exchange=exchange.name,
    task_default_routing_key="limits",
    task_acks_late=True,
    broker_transport_options={"visibility_timeout": settings.visibility_timeout},
    result_expires=settings.result_expires,
    timezone=settings.timezone,
    enable_utc=False,  # используем локальную таймзону
)

# Роутинг по задачам
celery.conf.task_routes = {
    "app.tasks.limits.recompute_limits": {"queue": q_limits.name, "routing_key": "limits"},
    "app.tasks.reports.nightly_reports": {"queue": q_reports.name, "routing_key": "reports"},
    "app.tasks.backups.run_backup":      {"queue": q_backups.name, "routing_key": "backups"},
    "app.tasks.prices.load_price_lists": {"queue": q_prices.name, "routing_key": "prices"},
    "app.tasks.antifraud.scan_signals":  {"queue": q_antifraud.name, "routing_key": "antifraud"},
}

# DEAD LETTER (простой вариант): кладём JSON в Redis List `neft:celery:dead`
from redis import Redis

def _dead_letter_push(payload: Dict[str, Any]) -> None:
    key = f"{settings.queue_prefix}:dead"
    r = Redis.from_url(settings.redis_url)
    r.lpush(key, json.dumps(payload, ensure_ascii=False))

@signals.task_failure.connect
def _on_task_failure(sender=None, exception=None, traceback=None, **kwargs):
    info = {
        "task": getattr(sender, "name", str(sender)),
        "exception": repr(exception),
        "when": int(time.time()),
        "kwargs": kwargs.get("kwargs"),
        "args": kwargs.get("args"),
    }
    _dead_letter_push(info)

# Beat schedule (периодика)
celery.conf.beat_schedule = {
    "recompute-limits-1min": {
        "task": "app.tasks.limits.recompute_limits",
        "schedule": 60.0,  # каждую минуту
        "options": {"queue": q_limits.name},
    },
    "nightly-reports-2am": {
        "task": "app.tasks.reports.nightly_reports",
        "schedule": {"type": "crontab", "minute": 0, "hour": 2},  # 02:00
        "options": {"queue": q_reports.name},
    },
    "run-backup-3am": {
        "task": "app.tasks.backups.run_backup",
        "schedule": {"type": "crontab", "minute": 0, "hour": 3},  # 03:00
        "options": {"queue": q_backups.name},
    },
    "load-prices-every-15min": {
        "task": "app.tasks.prices.load_price_lists",
        "schedule": 900.0,  # каждые 15 минут
        "options": {"queue": q_prices.name},
    },
    "antifraud-scan-5min": {
        "task": "app.tasks.antifraud.scan_signals",
        "schedule": 300.0,  # каждые 5 минут
        "options": {"queue": q_antifraud.name},
    },
}

# Утилита для безопасного crontab (чтобы celery beat понимал dict-формат выше)
from celery.schedules import crontab
def _fix_crontab():
    for name, item in list(celery.conf.beat_schedule.items()):
        sched = item.get("schedule")
        if isinstance(sched, dict) and sched.get("type") == "crontab":
            celery.conf.beat_schedule[name]["schedule"] = crontab(
                minute=sched.get("minute", 0),
                hour=sched.get("hour", 0),
                day_of_week=sched.get("day_of_week", "*"),
                day_of_month=sched.get("day_of_month", "*"),
                month_of_year=sched.get("month_of_year", "*"),
            )
_fix_crontab()
