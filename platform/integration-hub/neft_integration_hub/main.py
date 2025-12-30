from __future__ import annotations

import logging
from typing import Callable
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from sqlalchemy.orm import Session

from neft_integration_hub.celery_app import celery_app
from neft_integration_hub.db import get_db, init_db
from neft_integration_hub.models import EdoDocument, WebhookEndpoint
from neft_integration_hub.schemas import (
    DispatchRequest,
    DispatchResponse,
    EdoDocumentResponse,
    WebhookDeliveryResponse,
    WebhookEndpointCreate,
    WebhookEndpointResponse,
    WebhookEndpointSecretResponse,
    WebhookOwner,
    WebhookRotateSecretResponse,
    WebhookSubscriptionCreate,
    WebhookSubscriptionResponse,
    WebhookTestResponse,
)
from neft_integration_hub.services.edo_service import dispatch_request
from neft_integration_hub.services.webhooks import (
    build_event_envelope,
    create_endpoint,
    create_subscription,
    enqueue_delivery,
    list_deliveries,
    list_endpoints,
    rotate_secret,
)
from neft_integration_hub.settings import get_settings

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


@app.post("/v1/webhooks/endpoints", response_model=WebhookEndpointSecretResponse)
def create_webhook_endpoint(payload: WebhookEndpointCreate, db: Session = Depends(get_db)) -> WebhookEndpointSecretResponse:
    endpoint, secret = create_endpoint(
        db,
        owner_type=payload.owner_type,
        owner_id=payload.owner_id,
        url=payload.url,
        signing_algo=payload.signing_algo,
    )
    return WebhookEndpointSecretResponse(
        id=endpoint.id,
        owner_type=endpoint.owner_type,
        owner_id=endpoint.owner_id,
        url=endpoint.url,
        status=endpoint.status,
        signing_algo=endpoint.signing_algo,
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
        secret=secret,
    )


@app.get("/v1/webhooks/endpoints", response_model=list[WebhookEndpointResponse])
def get_webhook_endpoints(
    owner_type: str | None = None,
    owner_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[WebhookEndpointResponse]:
    endpoints = list_endpoints(db, owner_type=owner_type, owner_id=owner_id)
    return [
        WebhookEndpointResponse(
            id=endpoint.id,
            owner_type=endpoint.owner_type,
            owner_id=endpoint.owner_id,
            url=endpoint.url,
            status=endpoint.status,
            signing_algo=endpoint.signing_algo,
            created_at=endpoint.created_at,
            updated_at=endpoint.updated_at,
        )
        for endpoint in endpoints
    ]


@app.post("/v1/webhooks/endpoints/{endpoint_id}/test", response_model=WebhookTestResponse)
def test_webhook_endpoint(endpoint_id: str, db: Session = Depends(get_db)) -> WebhookTestResponse:
    endpoint = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="endpoint_not_found")
    event_id = str(uuid4())
    envelope = build_event_envelope(
        event_id=event_id,
        event_type="webhook.test",
        correlation_id=event_id,
        owner=WebhookOwner(type=endpoint.owner_type, id=endpoint.owner_id),
        payload={"message": "test"},
    )
    delivery = enqueue_delivery(db, endpoint=endpoint, envelope=envelope)
    celery_app.send_task("webhook.deliver", args=[delivery.id])
    return WebhookTestResponse(event_id=event_id, delivery_id=delivery.id, status=delivery.status)


@app.post("/v1/webhooks/subscriptions", response_model=WebhookSubscriptionResponse)
def create_webhook_subscription(
    payload: WebhookSubscriptionCreate,
    db: Session = Depends(get_db),
) -> WebhookSubscriptionResponse:
    endpoint = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == payload.endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="endpoint_not_found")
    subscription = create_subscription(
        db,
        endpoint_id=payload.endpoint_id,
        event_type=payload.event_type,
        schema_version=payload.schema_version,
        filters=payload.filters,
        enabled=payload.enabled,
    )
    return WebhookSubscriptionResponse(
        id=subscription.id,
        endpoint_id=subscription.endpoint_id,
        event_type=subscription.event_type,
        schema_version=subscription.schema_version,
        filters=subscription.filters,
        enabled=subscription.enabled,
    )


@app.get("/v1/webhooks/deliveries", response_model=list[WebhookDeliveryResponse])
def get_webhook_deliveries(
    endpoint_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[WebhookDeliveryResponse]:
    deliveries = list_deliveries(db, endpoint_id=endpoint_id, status=status)
    return [
        WebhookDeliveryResponse(
            id=delivery.id,
            endpoint_id=delivery.endpoint_id,
            event_id=delivery.event_id,
            event_type=delivery.event_type,
            attempt=delivery.attempt,
            status=delivery.status,
            last_http_status=delivery.last_http_status,
            last_error=delivery.last_error,
            next_retry_at=delivery.next_retry_at,
        )
        for delivery in deliveries
    ]


@app.post("/v1/webhooks/endpoints/{endpoint_id}/rotate-secret", response_model=WebhookRotateSecretResponse)
def rotate_webhook_secret(endpoint_id: str, db: Session = Depends(get_db)) -> WebhookRotateSecretResponse:
    endpoint = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="endpoint_not_found")
    secret = rotate_secret(db, endpoint)
    return WebhookRotateSecretResponse(endpoint_id=endpoint.id, secret=secret)


def _count_in_status(db: Session, status: str) -> int:
    return db.query(EdoDocument).filter(EdoDocument.status == status).count()


__all__ = ["app"]
