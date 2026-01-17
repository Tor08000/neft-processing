from __future__ import annotations

from datetime import datetime, timezone

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.models.helpdesk import HelpdeskOutbox, HelpdeskOutboxStatus
from app.services.helpdesk_service import deliver_helpdesk_outbox


@celery_client.task(name="helpdesk.process_outbox", bind=True, max_retries=6, default_retry_delay=60)
def process_helpdesk_outbox(self, outbox_id: str) -> dict:
    session = get_sessionmaker()()
    try:
        outbox = session.get(HelpdeskOutbox, outbox_id)
        if not outbox:
            return {"status": "not_found", "outbox_id": outbox_id}
        if outbox.status == HelpdeskOutboxStatus.SENT:
            return {"status": "skipped", "outbox_id": outbox_id}
        now = datetime.now(timezone.utc)
        if outbox.next_retry_at and outbox.next_retry_at > now:
            return {"status": "scheduled", "outbox_id": outbox_id}

        status, retry_after = deliver_helpdesk_outbox(session, outbox=outbox)
        session.commit()

        if retry_after:
            raise self.retry(countdown=retry_after)
        return {"status": status.value.lower(), "outbox_id": outbox_id}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["process_helpdesk_outbox"]
