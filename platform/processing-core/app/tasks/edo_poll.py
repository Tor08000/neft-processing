from __future__ import annotations

import logging
import os

from app.celery_client import celery_client
from app.db import SessionLocal
from app.domains.documents.edo_service import DocumentEdoService
from app.domains.documents.models import DocumentEdoState
from app.domains.documents.repo import DocumentsRepository

logger = logging.getLogger(__name__)


class _NoopMetric:
    def inc(self, value: float = 1) -> None:
        return None

    def set(self, value: float) -> None:
        return None

    def labels(self, **_: str) -> "_NoopMetric":
        return self


_METRICS: tuple[object, object, object] | None = None


def _metrics_enabled() -> bool:
    return os.getenv("METRICS_ENABLED", "1").strip().lower() not in {"0", "false", "off", "no"}


def _get_metrics() -> tuple[object, object, object]:
    global _METRICS
    if _METRICS is not None:
        return _METRICS

    if not _metrics_enabled():
        noop = _NoopMetric()
        _METRICS = (noop, noop, noop)
        return _METRICS

    try:
        from prometheus_client import Counter, Gauge
    except ModuleNotFoundError:
        logger.warning("prometheus_client is unavailable, EDO metrics are disabled")
        noop = _NoopMetric()
        _METRICS = (noop, noop, noop)
        return _METRICS

    _METRICS = (
        Counter("edo_poll_success_total", "Successful EDO poll updates"),
        Counter("edo_poll_fail_total", "Failed EDO poll updates"),
        Gauge("edo_state_by_status", "EDO states by status", ["status"]),
    )
    return _METRICS


@celery_client.task(name="edo.poll_document_edo_states")
def poll_document_edo_states() -> dict[str, int]:
    edo_poll_success_total, edo_poll_fail_total, edo_state_by_status = _get_metrics()

    db = SessionLocal()
    try:
        service = DocumentEdoService(repo=DocumentsRepository(db=db))
        result = service.poll_states(limit=100)
        if result["success"]:
            edo_poll_success_total.inc(result["success"])
        if result["failed"]:
            edo_poll_fail_total.inc(result["failed"])
        rows = db.query(DocumentEdoState.edo_status).all()
        counts: dict[str, int] = {}
        for (status,) in rows:
            counts[status] = counts.get(status, 0) + 1
        for status, value in counts.items():
            edo_state_by_status.labels(status=status).set(value)
        return result
    finally:
        db.close()
