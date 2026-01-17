from __future__ import annotations

from datetime import datetime, timezone

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.models.email_outbox import EmailOutbox, EmailOutboxStatus
from app.services.email_service import deliver_outbox_email


@celery_client.task(name="emails.send_outbox", bind=True, max_retries=6, default_retry_delay=60)
def send_email_outbox(self, outbox_id: str) -> dict:
    session = get_sessionmaker()()
    try:
        outbox = session.get(EmailOutbox, outbox_id)
        if not outbox:
            return {"status": "not_found", "outbox_id": outbox_id}
        if outbox.status == EmailOutboxStatus.SENT:
            return {"status": "skipped", "outbox_id": outbox_id}
        now = datetime.now(timezone.utc)
        if outbox.next_retry_at and outbox.next_retry_at > now:
            return {"status": "scheduled", "outbox_id": outbox_id}

        result, retry_after = deliver_outbox_email(session, outbox=outbox)
        session.commit()

        if retry_after:
            raise self.retry(countdown=retry_after)
        return {"status": result.status.lower(), "outbox_id": outbox_id}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["send_email_outbox"]
