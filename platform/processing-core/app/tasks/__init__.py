"""Celery tasks for billing and invoicing."""

from __future__ import annotations

from app.celery_client import celery_client

try:  # pragma: no cover - optional task modules
    import app.tasks.accounting_exports  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.legal_integrations  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.fraud  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.sla_escalations  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.case_escalations  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.fleet_intelligence  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.fleet_control  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.bi_analytics  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.bi_clickhouse  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.export_jobs  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.report_schedules  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.subscription_billing  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.billing_dunning  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.email_outbox  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.helpdesk_outbox  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.service_slo  # noqa: F401
except Exception:
    pass


try:  # pragma: no cover - optional task modules
    import app.tasks.geo_metrics  # noqa: F401
except Exception:
    pass


try:  # pragma: no cover - optional task modules
    import app.tasks.geo_tiles  # noqa: F401
except Exception:
    pass



try:  # pragma: no cover - optional task modules
    import app.tasks.geo_clickhouse  # noqa: F401
except Exception:
    pass


try:  # pragma: no cover - optional task modules
    import app.tasks.station_automation  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.commercial_margin  # noqa: F401
except Exception:
    pass

@celery_client.task(name="workers.ping")
def ping(x: int = 1) -> dict:
    """Simple ping task to validate Celery connectivity."""

    return {"pong": x}


__all__ = ["ping"]
