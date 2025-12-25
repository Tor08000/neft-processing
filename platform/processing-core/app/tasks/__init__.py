"""Celery tasks for billing and invoicing."""

from __future__ import annotations

from app.celery_client import celery_client

try:  # pragma: no cover - optional task modules
    import app.tasks.accounting_exports  # noqa: F401
except Exception:
    pass


@celery_client.task(name="workers.ping")
def ping(x: int = 1) -> dict:
    """Simple ping task to validate Celery connectivity."""

    return {"pong": x}


__all__ = ["ping"]
