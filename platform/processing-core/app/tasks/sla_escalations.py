from __future__ import annotations

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.services.audit_service import AuditService
from app.services.ops.escalations import scan_explain_sla_expiry
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


@celery_client.task(name="ops.scan_sla_expiry")
def scan_sla_expiry_task() -> dict[str, int]:
    session = get_sessionmaker()()
    try:
        created = scan_explain_sla_expiry(session, audit=AuditService(session))
        session.commit()
        return {"created": len(created)}
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("ops.scan_sla_expiry_failed")
        raise
    finally:
        session.close()


__all__ = ["scan_sla_expiry_task"]
