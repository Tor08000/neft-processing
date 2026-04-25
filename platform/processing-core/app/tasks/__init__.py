"""Celery task package bootstrap."""

from __future__ import annotations

from app.celery_client import celery_client

OPTIONAL_TASK_MODULES = [
    "app.tasks.accounting_exports",
    "app.tasks.legal_integrations",
    "app.tasks.fraud",
    "app.tasks.sla_escalations",
    "app.tasks.case_escalations",
    "app.tasks.fleet_intelligence",
    "app.tasks.fleet_control",
    "app.tasks.bi_analytics",
    "app.tasks.bi_clickhouse",
    "app.tasks.export_jobs",
    "app.tasks.report_schedules",
    "app.tasks.subscription_billing",
    "app.tasks.billing_dunning",
    "app.tasks.email_outbox",
    "app.tasks.helpdesk_outbox",
    "app.tasks.notification_outbox",
    "app.tasks.service_slo",
    "app.tasks.geo_metrics",
    "app.tasks.geo_tiles",
    "app.tasks.geo_clickhouse",
    "app.tasks.station_automation",
    "app.tasks.commercial_margin",
    "app.tasks.commercial_elasticity",
    "app.tasks.commercial_price_recommendations",
    "app.tasks.document_packages",
    "app.tasks.edo_poll",
    "app.tasks.billing_pdf",
]


@celery_client.task(name="workers.ping")
def ping(x: int = 1) -> dict:
    """Simple ping task to validate Celery connectivity."""

    return {"pong": x}


__all__ = ["OPTIONAL_TASK_MODULES", "ping"]
