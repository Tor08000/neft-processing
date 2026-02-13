from __future__ import annotations

from app.celery_client import celery_client
from app.db import SessionLocal
from app.services.geo_metrics import geo_metrics_backfill


@celery_client.task(name="geo.metrics_backfill")
def geo_metrics_backfill_task(days: int = 7) -> dict[str, object]:
    with SessionLocal() as db:
        rebuilt = geo_metrics_backfill(db, days=days)
    return {"days": days, "rebuilt": [item.isoformat() for item in rebuilt]}


__all__ = ["geo_metrics_backfill_task"]
