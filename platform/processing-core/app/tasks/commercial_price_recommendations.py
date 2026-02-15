from __future__ import annotations

from app.celery_client import celery_client
from app.db import SessionLocal
from app.services.commercial_price_recommendations import build_price_recommendations


@celery_client.task(name="commercial.price_recommendations_build")
def commercial_price_recommendations_build(window_days: int = 90) -> dict[str, object]:
    with SessionLocal() as db:
        return build_price_recommendations(db, window_days=window_days)


__all__ = ["commercial_price_recommendations_build"]
