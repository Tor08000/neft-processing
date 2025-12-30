from __future__ import annotations

import logging
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.db import get_db, init_db
from app.models import EdoDocument
from app.schemas import DispatchRequest, DispatchResponse, EdoDocumentResponse
from app.services.edo_service import dispatch_request
from app.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

SERVICE_NAME = settings.service_name
SERVICE_VERSION = settings.service_version
METRIC_PREFIX = "integration_hub"

app = FastAPI(title="Integration Hub")

INTEGRATION_HUB_UP = Gauge(f"{METRIC_PREFIX}_up", "Integration hub up")
INTEGRATION_HUB_HTTP_REQUESTS_TOTAL = Counter(
    f"{METRIC_PREFIX}_http_requests_total",
    "Total HTTP requests handled by integration hub",
    ["method", "path", "status"],
)
EDO_JOBS_TOTAL = Counter(
    f"{METRIC_PREFIX}_edo_jobs_total",
    "EDO jobs by status",
    ["job", "status"],
)
EDO_DOCUMENTS_IN_STATUS = Gauge(
    f"{METRIC_PREFIX}_edo_documents_in_status",
    "EDO documents in status",
    ["status"],
)
EDO_PROVIDER_REQUESTS_TOTAL = Counter(
    f"{METRIC_PREFIX}_edo_provider_requests_total",
    "EDO provider requests",
    ["provider", "op", "status"],
)
EDO_FAILURES_TOTAL = Counter(
    f"{METRIC_PREFIX}_edo_failures_total",
    "EDO failures by provider and code",
    ["provider", "code"],
)

INTEGRATION_HUB_UP.set(1)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.middleware("http")
async def metrics_middleware(request: Request, call_next: Callable[[Request], Response]) -> Response:
    try:
        response = await call_next(request)
    except Exception:
        INTEGRATION_HUB_HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            path=request.url.path,
            status="500",
        ).inc()
        raise

    INTEGRATION_HUB_HTTP_REQUESTS_TOTAL.labels(
        method=request.method,
        path=request.url.path,
        status=str(response.status_code),
    ).inc()
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/edo/dispatch", response_model=DispatchResponse)
def edo_dispatch(payload: DispatchRequest, db: Session = Depends(get_db)) -> DispatchResponse:
    record = dispatch_request(db, payload)
    EDO_JOBS_TOTAL.labels(job="dispatch", status=record.status).inc()
    EDO_DOCUMENTS_IN_STATUS.labels(status=record.status).set(_count_in_status(db, record.status))
    celery_app.send_task("edo.send", args=[record.id])
    return DispatchResponse(status=record.status, edo_document_id=record.id)


@app.get("/v1/edo/documents/{edo_document_id}", response_model=EdoDocumentResponse)
def edo_document_status(edo_document_id: str, db: Session = Depends(get_db)) -> EdoDocumentResponse:
    record = db.query(EdoDocument).filter(EdoDocument.id == edo_document_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="edo_document_not_found")
    return EdoDocumentResponse(
        edo_document_id=record.id,
        document_id=record.document_id,
        signature_id=record.signature_id,
        provider=record.provider,
        status=record.status,
        provider_message_id=record.provider_message_id,
        provider_document_id=record.provider_document_id,
        attempt=record.attempt,
        last_error=record.last_error,
    )


def _count_in_status(db: Session, status: str) -> int:
    return db.query(EdoDocument).filter(EdoDocument.status == status).count()


__all__ = ["app"]
