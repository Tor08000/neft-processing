from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta

from celery.schedules import crontab

from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings

from .job_evidence import record_schedule_loaded, record_scheduler_heartbeat
from .settings import settings

logger = get_logger(__name__)

shared_settings = get_settings()


def _parse_time(value: str, default: tuple[int, int]) -> tuple[int, int]:
    if not value:
        return default
    try:
        hour, minute = value.split(":")
        return int(hour), int(minute)
    except ValueError:
        logger.warning("Invalid time format '%s', fallback to %s", value, default)
        return default


def _shift_time(base: tuple[int, int], hours: int) -> tuple[int, int]:
    base_time = datetime(2000, 1, 1, base[0], base[1])
    shifted = base_time + timedelta(hours=hours)
    return shifted.hour, shifted.minute


def _build_schedule() -> dict:
    billing_hour, billing_minute = _parse_time(shared_settings.NEFT_BILLING_DAILY_AT, (1, 0))
    clearing_hour, clearing_minute = _parse_time(shared_settings.NEFT_CLEARING_DAILY_AT, (2, 0))
    finalize_hour, finalize_minute = _shift_time(
        (billing_hour, billing_minute),
        shared_settings.NEFT_BILLING_FINALIZE_GRACE_HOURS,
    )

    return {
        "periodic-ping": {
            "task": "periodic.ping",
            "schedule": 60.0,
        },
        "apply-daily-limits": {
            "task": "limits.apply_daily_limits",
            "schedule": 3600.0,
        },
        "billing-daily-summaries": {
            "task": "billing.build_daily_summaries",
            "schedule": crontab(hour=billing_hour, minute=billing_minute),
        },
        "clearing-daily-batch": {
            "task": "clearing.build_daily_batch",
            "schedule": crontab(hour=clearing_hour, minute=clearing_minute),
        },
        "billing-finalize": {
            "task": "clearing.finalize_billing",
            "schedule": crontab(hour=finalize_hour, minute=finalize_minute),
        },
    }


_SCHEDULE = _build_schedule()
_HEARTBEAT_THREAD: threading.Thread | None = None


def _should_emit_scheduler_state() -> bool:
    role = os.getenv("ROLE", "")
    beat_flag = os.getenv("CELERY_BEAT", "")
    return role.lower() == "beat" or beat_flag.lower() in {"1", "true", "yes"}


def _start_heartbeat() -> None:
    global _HEARTBEAT_THREAD
    if _HEARTBEAT_THREAD and _HEARTBEAT_THREAD.is_alive():
        return

    def _loop() -> None:
        while True:
            try:
                record_scheduler_heartbeat()
            except Exception:
                logger.exception("[beat] heartbeat update failed")
            time.sleep(30)

    _HEARTBEAT_THREAD = threading.Thread(target=_loop, name="beat-heartbeat", daemon=True)
    _HEARTBEAT_THREAD.start()


def apply_schedule(celery_app) -> None:
    celery_app.conf.beat_schedule = _SCHEDULE
    celery_app.conf.timezone = settings.timezone

    if _should_emit_scheduler_state():
        task_count = len(celery_app.conf.beat_schedule or {})
        logger.info("[beat] schedule loaded: %s tasks", task_count)
        record_schedule_loaded(task_count)
        _start_heartbeat()


__all__ = ["apply_schedule"]
