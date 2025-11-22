from .tasks import celery

celery.conf.beat_schedule = {
    "reports-daily-every-60s": {
        "task": "reports.daily",
        "schedule": 60.0,
    },
    "billing-generate-invoices-every-5m": {
        "task": "billing.generate_invoices",
        "schedule": 300.0,
    },
    "holds-cleanup-every-2m": {
        "task": "holds.cleanup_expired",
        "schedule": 120.0,
    },
}
