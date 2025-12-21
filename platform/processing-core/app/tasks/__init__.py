"""Celery tasks for billing and invoicing."""

from __future__ import annotations

from app.celery_client import celery_client


@celery_client.task(name="workers.ping")
def ping(x: int = 1) -> dict:
    """Simple ping task to validate Celery connectivity."""

    return {"pong": x}


__all__ = ["ping"]
