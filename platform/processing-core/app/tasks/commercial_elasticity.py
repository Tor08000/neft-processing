from __future__ import annotations

from app.celery_client import celery_client
from app.db import SessionLocal
from app.services.commercial_elasticity import elasticity_compute


@celery_client.task(name="commercial.elasticity_compute")
def commercial_elasticity_compute(window_days: int = 90) -> dict[str, object]:
    db = SessionLocal()
    try:
        return elasticity_compute(db, window_days=window_days)
    finally:
        db.close()


__all__ = ["commercial_elasticity_compute"]
