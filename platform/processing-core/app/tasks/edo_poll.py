from __future__ import annotations

from prometheus_client import Counter, Gauge

from app.celery_client import celery_client
from app.db import SessionLocal
from app.domains.documents.edo_service import DocumentEdoService
from app.domains.documents.models import DocumentEdoState
from app.domains.documents.repo import DocumentsRepository

EDO_POLL_SUCCESS_TOTAL = Counter("edo_poll_success_total", "Successful EDO poll updates")
EDO_POLL_FAIL_TOTAL = Counter("edo_poll_fail_total", "Failed EDO poll updates")
EDO_STATE_BY_STATUS = Gauge("edo_state_by_status", "EDO states by status", ["status"])


@celery_client.task(name="edo.poll_document_edo_states")
def poll_document_edo_states() -> dict[str, int]:
    db = SessionLocal()
    try:
        service = DocumentEdoService(repo=DocumentsRepository(db=db))
        result = service.poll_states(limit=100)
        if result["success"]:
            EDO_POLL_SUCCESS_TOTAL.inc(result["success"])
        if result["failed"]:
            EDO_POLL_FAIL_TOTAL.inc(result["failed"])
        rows = db.query(DocumentEdoState.edo_status).all()
        counts: dict[str, int] = {}
        for (status,) in rows:
            counts[status] = counts.get(status, 0) + 1
        for status, value in counts.items():
            EDO_STATE_BY_STATUS.labels(status=status).set(value)
        return result
    finally:
        db.close()
