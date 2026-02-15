# services/core-api/app/celery_client.py
from __future__ import annotations

import os
from celery import Celery
from celery.schedules import crontab

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
    task_routes={
        "billing.generate_monthly_invoices": {"queue": "billing"},
        "billing.generate_invoice_pdf": {"queue": "pdf"},
        "billing.generate_subscription_invoices": {"queue": "billing"},
        "billing.overdue_check": {"queue": "billing"},
        "billing.dunning_scan": {"queue": "billing"},
        "billing.suspend_overdue": {"queue": "billing"},
        "commercial.elasticity_compute": {"queue": "celery"},
        "commercial.price_recommendations_build": {"queue": "celery"},
    },
    beat_schedule={
        "billing_generate_monthly": {
            "task": "billing.generate_subscription_invoices",
            "schedule": crontab(day_of_month="1", hour=1, minute=0),
        },
        "billing_overdue_check": {
            "task": "billing.overdue_check",
            "schedule": crontab(minute="*/30"),
        },
        "billing_dunning_scan": {
            "task": "billing.dunning_scan",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        "billing_suspend_overdue": {
            "task": "billing.suspend_overdue",
            "schedule": crontab(hour=2, minute=0),
        },
        "ops.scan_sla_expiry": {
            "task": "ops.scan_sla_expiry",
            "schedule": crontab(minute="*/5"),
        },
        "cases.evaluate_escalations": {
            "task": "cases.evaluate_escalations",
            "schedule": crontab(minute="*/2"),
        },
        "fleet_intelligence.compute_daily_aggregates": {
            "task": "fleet_intelligence.compute_daily_aggregates",
            "schedule": crontab(hour=2, minute=30),
        },
        "fleet_intelligence.compute_scores": {
            "task": "fleet_intelligence.compute_scores",
            "schedule": crontab(hour=3, minute=0),
        },
        "fleet_intelligence.compute_trends_daily": {
            "task": "fleet_intelligence.compute_trends_daily",
            "schedule": crontab(hour=3, minute=30),
        },
        "fleet_control.nightly": {
            "task": "fleet_control.nightly",
            "schedule": crontab(hour=4, minute=0),
        },
        "reports.run_report_schedules": {
            "task": "reports.run_report_schedules",
            "schedule": crontab(minute="*/2"),
        },
        "exports.cleanup_expired_exports": {
            "task": "exports.cleanup_expired_exports",
            "schedule": crontab(hour="*/6", minute=15),
        },
        "slo.evaluate": {
            "task": "slo.evaluate",
            "schedule": crontab(minute="*/15"),
        },
        "geo.metrics_backfill": {
            "task": "geo.metrics_backfill",
            "schedule": crontab(hour=2, minute=30),
        },
        "geo.tiles_refresh": {
            "task": "geo.tiles_refresh",
            "schedule": crontab(hour=2, minute=45),
        },
        "geo.tiles_backfill_weekly": {
            "task": "geo.tiles_backfill",
            "schedule": crontab(day_of_week="sun", hour=3, minute=15),
        },
        "geo.tiles_overlays_refresh": {
            "task": "geo.tiles_overlays_refresh",
            "schedule": crontab(hour=3, minute=0),
        },
        "geo.tiles_overlays_backfill_weekly": {
            "task": "geo.tiles_overlays_backfill",
            "schedule": crontab(day_of_week="sun", hour=3, minute=30),
        },
        "geo.clickhouse_sync": {
            "task": "geo.clickhouse_sync",
            "schedule": crontab(minute="*/5"),
        },
        "commercial.margin_build_daily": {
            "task": "commercial.margin_build_daily",
            "schedule": crontab(hour=3, minute=30),
        },
        "commercial.elasticity_compute_30": {
            "task": "commercial.elasticity_compute",
            "schedule": crontab(hour=3, minute=40),
            "args": (30,),
        },
        "commercial.elasticity_compute_90": {
            "task": "commercial.elasticity_compute",
            "schedule": crontab(hour=3, minute=50),
            "args": (90,),
        },
        "commercial.price_recommendations_build": {
            "task": "commercial.price_recommendations_build",
            "schedule": crontab(hour=5, minute=0),
            "args": (90,),
        },
        "ops.station_health_evaluate": {
            "task": "ops.station_health_evaluate",
            "schedule": crontab(minute="*/5"),
        },
        "ops.station_risk_escalate": {
            "task": "ops.station_risk_escalate",
            "schedule": crontab(minute="*/30"),
        },
        "ops.station_risk_downgrade_daily": {
            "task": "ops.station_risk_downgrade_daily",
            "schedule": crontab(hour=3, minute=10),
        },
    },
)

# Register billing tasks
try:  # pragma: no cover - optional celery runtime
    import app.tasks  # noqa: F401
    import app.tasks.billing_pdf  # noqa: F401
except Exception:
    pass
