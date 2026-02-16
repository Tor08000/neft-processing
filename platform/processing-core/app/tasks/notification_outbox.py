from __future__ import annotations

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.services.client_invitation_notifications import process_notification_outbox


@celery_client.task(name="notifications.process_outbox")
def process_outbox(limit: int = 50) -> dict:
    session = get_sessionmaker()()
    try:
        sent = process_notification_outbox(session, limit=limit)
        session.commit()
        return {"status": "ok", "sent": sent}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["process_outbox"]
