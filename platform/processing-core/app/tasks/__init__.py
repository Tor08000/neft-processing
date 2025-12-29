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
    import app.tasks.fleet_intelligence  # noqa: F401
except Exception:
    pass

try:  # pragma: no cover - optional task modules
    import app.tasks.fleet_control  # noqa: F401
except Exception:
    pass


@celery_client.task(name="workers.ping")
def ping(x: int = 1) -> dict:
    """Simple ping task to validate Celery connectivity."""

    return {"pong": x}


__all__ = ["ping"]
