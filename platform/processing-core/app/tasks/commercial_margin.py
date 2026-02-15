from __future__ import annotations

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.services.commercial_margin import margin_build_daily


@celery_client.task(name="commercial.margin_build_daily")
def commercial_margin_build_daily(days_back: int = 7) -> dict[str, object]:
    session_local = get_sessionmaker()
    with session_local() as db:
        rebuilt = margin_build_daily(db, days_back=days_back)
    return {"days_back": days_back, "rebuilt_days": [d.isoformat() for d in rebuilt], "rebuilt": len(rebuilt)}


__all__ = ["commercial_margin_build_daily"]
