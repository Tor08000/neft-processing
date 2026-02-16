from __future__ import annotations

import logging
from typing import Callable
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from sqlalchemy.orm import Session

from neft_integration_hub.celery_app import celery_app
from neft_integration_hub.db import get_db, init_db
from neft_integration_hub.metrics import (
    WEBHOOK_ALERTS_ACTIVE_TOTAL,
    WEBHOOK_DELIVERY_SUCCESS_RATIO,
    WEBHOOK_PAUSED_ENDPOINTS_TOTAL,
    WEBHOOK_REPLAY_SCHEDULED_TOTAL,
)
from neft_integration_hub.models import EdoDocument, EdoStubStatus, WebhookAlert, WebhookAlertType, WebhookEndpoint
from neft_integration_hub.schemas import (
    DispatchRequest,
    DispatchResponse,
    EdoDocumentResponse,
    EdoStubSendRequest,
    EdoStubSendResponse,
    EdoStubSimulateRequest,
    EdoStubStatusResponse,
    WebhookAlertResponse,
    WebhookDeliveryResponse,
    WebhookEndpointCreate,
    WebhookEndpointResponse,
    WebhookEndpointSecretResponse,
    WebhookIntakeRequest,
    WebhookIntakeResponse,
    WebhookOwner,
    WebhookPauseRequest,
    WebhookReplayRequest,
    WebhookReplayResponse,
    WebhookRotateSecretResponse,
    WebhookSlaResponse,
    WebhookSubscriptionCreate,
    WebhookSubscriptionResponse,
    WebhookTestDeliveryRequest,
    WebhookTestResponse,
)
from neft_integration_hub.services.edo_service import dispatch_request
from neft_integration_hub.services.edo_stub import create_stub_document, get_stub_document, simulate_status
from neft_integration_hub.services.webhook_intake import record_intake_event, verify_signature
from neft_integration_hub.services.webhooks import (
    build_event_envelope,
    compute_sla,
    create_endpoint,
    create_subscription,
    evaluate_alerts,
    enqueue_delivery,
    list_deliveries,
    list_endpoints,
    pause_endpoint,
    resume_endpoint,
    rotate_secret,
    schedule_replay,
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
    logger.info(
        "running in %s mode",
        settings.app_env.upper(),
        extra={"app_env": settings.app_env, "use_stub_edo": settings.use_stub_edo},
    )


@app.middleware("http")
async def request_context_middleware(request: Request, call_next: Callable[[Request], Response]) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    trace_id = request.headers.get("X-Trace-ID") or request_id
    request.state.request_id = request_id
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Trace-ID"] = trace_id
    return response


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


def _log_intake(source: str, payload: WebhookIntakeRequest, request: Request, verified: bool) -> None:
    logger.info(
        "webhook.intake",
        extra={
            "source": source,
            "event_type": payload.event_type,
            "event_id": payload.event_id,
            "request_id": getattr(request.state, "request_id", None),
            "trace_id": getattr(request.state, "trace_id", None),
            "verified": verified,
        },
    )


async def _handle_webhook_intake(
    source: str,
    payload: WebhookIntakeRequest,
    request: Request,
    db: Session,
) -> WebhookIntakeResponse:
    raw_body = await request.body()
    signature_header = request.headers.get("X-Webhook-Signature")
    verified = False
    if signature_header:
        verified, _normalized = verify_signature(raw_body, signature_header, settings.webhook_intake_secret)
        if not verified:
            raise HTTPException(status_code=401, detail="invalid_signature")
    elif not settings.webhook_allow_unsigned:
        raise HTTPException(status_code=401, detail="signature_required")

    record_intake_event(
        db,
        source=source,
        event_type=payload.event_type,
        payload=payload.payload,
        event_id=payload.event_id,
        signature=signature_header,
        verified=verified,
        request_id=getattr(request.state, "request_id", None),
        trace_id=getattr(request.state, "trace_id", None),
    )
    _log_intake(source, payload, request, verified)
    return WebhookIntakeResponse(event_id=payload.event_id, status="accepted", verified=verified)


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


@app.post("/v1/edo/send", response_model=EdoStubSendResponse)
def edo_stub_send(payload: EdoStubSendRequest, request: Request, db: Session = Depends(get_db)) -> EdoStubSendResponse:
    if not settings.use_stub_edo:
        raise HTTPException(status_code=404, detail="edo_stub_disabled")
    record = create_stub_document(
        db,
        document_id=payload.doc_id,
        counterparty=payload.counterparty,
        payload_ref=payload.payload_ref,
        meta=payload.meta,
    )
    logger.info(
        "edo.stub.send",
        extra={
            "edo_doc_id": record.id,
            "document_id": record.document_id,
            "status": record.status,
            "request_id": getattr(request.state, "request_id", None),
            "trace_id": getattr(request.state, "trace_id", None),
        },
    )
    return EdoStubSendResponse(edo_doc_id=record.id, status=record.status)


@app.get("/v1/edo/{edo_doc_id}/status", response_model=EdoStubStatusResponse)
def edo_stub_status(edo_doc_id: str, request: Request, db: Session = Depends(get_db)) -> EdoStubStatusResponse:
    if not settings.use_stub_edo:
        raise HTTPException(status_code=404, detail="edo_stub_disabled")
    record = get_stub_document(db, edo_doc_id)
    if not record:
        raise HTTPException(status_code=404, detail="edo_stub_document_not_found")
    logger.info(
        "edo.stub.status",
        extra={
            "edo_doc_id": record.id,
            "status": record.status,
            "request_id": getattr(request.state, "request_id", None),
            "trace_id": getattr(request.state, "trace_id", None),
        },
    )
    return EdoStubStatusResponse(edo_doc_id=record.id, status=record.status)


@app.post("/v1/edo/{edo_doc_id}/simulate", response_model=EdoStubStatusResponse)
def edo_stub_simulate(
    edo_doc_id: str,
    payload: EdoStubSimulateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> EdoStubStatusResponse:
    if not settings.use_stub_edo:
        raise HTTPException(status_code=404, detail="edo_stub_disabled")
    try:
        status = EdoStubStatus(payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_status") from exc
    record = simulate_status(db, edo_doc_id, status, note=payload.note)
    if not record:
        raise HTTPException(status_code=404, detail="edo_stub_document_not_found")
    logger.info(
        "edo.stub.simulate",
        extra={
            "edo_doc_id": record.id,
            "status": record.status,
            "request_id": getattr(request.state, "request_id", None),
            "trace_id": getattr(request.state, "trace_id", None),
        },
    )
    return EdoStubStatusResponse(edo_doc_id=record.id, status=record.status)


@app.post("/v1/webhooks/client/events", response_model=WebhookIntakeResponse)
async def webhook_client_events(
    payload: WebhookIntakeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> WebhookIntakeResponse:
    return await _handle_webhook_intake("client", payload, request, db)


@app.post("/v1/webhooks/partner/events", response_model=WebhookIntakeResponse)
async def webhook_partner_events(
    payload: WebhookIntakeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> WebhookIntakeResponse:
    return await _handle_webhook_intake("partner", payload, request, db)


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
        delivery_paused=endpoint.delivery_paused,
        paused_at=endpoint.paused_at,
        paused_reason=endpoint.paused_reason,
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
            delivery_paused=endpoint.delivery_paused,
            paused_at=endpoint.paused_at,
            paused_reason=endpoint.paused_reason,
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


@app.post("/v1/webhooks/test-delivery", response_model=WebhookTestResponse)
def test_webhook_delivery(
    payload: WebhookTestDeliveryRequest,
    db: Session = Depends(get_db),
) -> WebhookTestResponse:
    endpoint = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == payload.endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="endpoint_not_found")
    event_id = str(uuid4())
    envelope = build_event_envelope(
        event_id=event_id,
        event_type=payload.event_type or "webhook.test",
        correlation_id=event_id,
        owner=WebhookOwner(type=endpoint.owner_type, id=endpoint.owner_id),
        payload=payload.payload or {"message": "test"},
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
            occurred_at=delivery.occurred_at,
            latency_ms=delivery.latency_ms,
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


@app.post("/v1/webhooks/endpoints/{endpoint_id}/pause", response_model=WebhookEndpointResponse)
def pause_webhook_endpoint(
    endpoint_id: str,
    payload: WebhookPauseRequest,
    db: Session = Depends(get_db),
) -> WebhookEndpointResponse:
    endpoint = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="endpoint_not_found")
    endpoint = pause_endpoint(db, endpoint, payload.reason)
    WEBHOOK_PAUSED_ENDPOINTS_TOTAL.labels(endpoint_id=endpoint.id, partner_id=endpoint.owner_id).set(1)
    return WebhookEndpointResponse(
        id=endpoint.id,
        owner_type=endpoint.owner_type,
        owner_id=endpoint.owner_id,
        url=endpoint.url,
        status=endpoint.status,
        signing_algo=endpoint.signing_algo,
        delivery_paused=endpoint.delivery_paused,
        paused_at=endpoint.paused_at,
        paused_reason=endpoint.paused_reason,
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
    )


@app.post("/v1/webhooks/endpoints/{endpoint_id}/resume", response_model=WebhookEndpointResponse)
def resume_webhook_endpoint(endpoint_id: str, db: Session = Depends(get_db)) -> WebhookEndpointResponse:
    endpoint = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="endpoint_not_found")
    endpoint = resume_endpoint(db, endpoint)
    WEBHOOK_PAUSED_ENDPOINTS_TOTAL.labels(endpoint_id=endpoint.id, partner_id=endpoint.owner_id).set(0)
    return WebhookEndpointResponse(
        id=endpoint.id,
        owner_type=endpoint.owner_type,
        owner_id=endpoint.owner_id,
        url=endpoint.url,
        status=endpoint.status,
        signing_algo=endpoint.signing_algo,
        delivery_paused=endpoint.delivery_paused,
        paused_at=endpoint.paused_at,
        paused_reason=endpoint.paused_reason,
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
    )


@app.post("/v1/webhooks/endpoints/{endpoint_id}/replay", response_model=WebhookReplayResponse)
def replay_webhook_deliveries(
    endpoint_id: str,
    payload: WebhookReplayRequest,
    db: Session = Depends(get_db),
) -> WebhookReplayResponse:
    endpoint = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="endpoint_not_found")
    replay, scheduled = schedule_replay(
        db,
        endpoint=endpoint,
        from_at=payload.from_at,
        to_at=payload.to_at,
        event_types=payload.event_types,
        only_failed=payload.only_failed,
        created_by=endpoint.owner_id,
    )
    WEBHOOK_REPLAY_SCHEDULED_TOTAL.labels(endpoint_id=endpoint.id, partner_id=endpoint.owner_id).inc(scheduled)
    return WebhookReplayResponse(replay_id=replay.id, scheduled_deliveries=scheduled)


@app.get("/v1/webhooks/endpoints/{endpoint_id}/sla", response_model=WebhookSlaResponse)
def get_webhook_sla(endpoint_id: str, window: str = "15m", db: Session = Depends(get_db)) -> WebhookSlaResponse:
    endpoint = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="endpoint_not_found")
    try:
        success_ratio, avg_latency_ms, sla_breaches, _total = compute_sla(db, endpoint=endpoint, window=window)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_window")
    WEBHOOK_DELIVERY_SUCCESS_RATIO.labels(
        endpoint_id=endpoint.id, partner_id=endpoint.owner_id, window=window
    ).set(success_ratio)
    alerts = evaluate_alerts(db, endpoint=endpoint)
    _sync_alert_metrics(endpoint.id, endpoint.owner_id, alerts)
    return WebhookSlaResponse(
        window=window,
        success_ratio=round(success_ratio, 2),
        avg_latency_ms=avg_latency_ms,
        sla_breaches=sla_breaches,
    )


@app.get("/v1/webhooks/endpoints/{endpoint_id}/alerts", response_model=list[WebhookAlertResponse])
def get_webhook_alerts(endpoint_id: str, db: Session = Depends(get_db)) -> list[WebhookAlertResponse]:
    endpoint = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="endpoint_not_found")
    alerts = (
        db.query(WebhookAlert)
        .filter(WebhookAlert.endpoint_id == endpoint.id)
        .filter(WebhookAlert.resolved_at.is_(None))
        .order_by(WebhookAlert.created_at.desc())
        .all()
    )
    _sync_alert_metrics(endpoint.id, endpoint.owner_id, alerts)
    return [
        WebhookAlertResponse(
            id=alert.id,
            type=alert.type,
            window=alert.window,
            created_at=alert.created_at,
        )
        for alert in alerts
    ]


def _sync_alert_metrics(endpoint_id: str, partner_id: str, alerts: list[WebhookAlert]) -> None:
    active_keys = {(alert.type, alert.window) for alert in alerts}
    for alert_type in WebhookAlertType:
        WEBHOOK_ALERTS_ACTIVE_TOTAL.labels(
            endpoint_id=endpoint_id,
            partner_id=partner_id,
            type=alert_type.value,
            window="30m",
        ).set(1 if (alert_type.value, "30m") in active_keys else 0)


def _count_in_status(db: Session, status: str) -> int:
    return db.query(EdoDocument).filter(EdoDocument.status == status).count()


__all__ = ["app"]

from datetime import datetime, timezone

from fastapi import Header


def _require_internal_token(x_internal_token: str | None = Header(default=None, alias="X-Internal-Token")) -> None:
    if settings.internal_token and x_internal_token != settings.internal_token:
        raise HTTPException(status_code=401, detail="invalid_internal_token")


@app.post("/v1/logistics/fleet/list")
def logistics_fleet_list(payload: dict, _auth: None = Depends(_require_internal_token)) -> dict:
    limit = int(payload.get("limit", 50))
    offset = int(payload.get("offset", 0))
    return {"ok": True, "request_id": str(uuid4()), "items": [], "total": 0, "limit": limit, "offset": offset}


@app.post("/v1/logistics/fleet/upsert")
def logistics_fleet_upsert(payload: dict, _auth: None = Depends(_require_internal_token)) -> dict:
    vehicle = {
        "vehicle_id": str(payload.get("vehicle_id", "vehicle-demo")),
        "plate_number": str(payload.get("plate_number", "A000AA00")),
        "kind": str(payload.get("kind", "truck")),
        "status": str(payload.get("status", "active")),
    }
    return {"ok": True, "request_id": str(uuid4()), "vehicle": vehicle}


@app.post("/v1/logistics/trips/create")
def logistics_trip_create(payload: dict, _auth: None = Depends(_require_internal_token)) -> dict:
    trip_id = str(payload.get("trip_id", "trip-demo"))
    return {"ok": True, "request_id": str(uuid4()), "trip_id": trip_id, "status": "created"}


@app.get("/v1/logistics/trips/{trip_id}/status")
def logistics_trip_status(trip_id: str, _auth: None = Depends(_require_internal_token)) -> dict:
    return {"ok": True, "request_id": str(uuid4()), "trip_id": trip_id, "status": "created", "updated_at": datetime.now(timezone.utc).isoformat()}


@app.post("/v1/logistics/fuel/consumption")
def logistics_fuel_consumption(payload: dict, _auth: None = Depends(_require_internal_token)) -> dict:
    trip_id = str(payload.get("trip_id", "trip-demo"))
    distance_km = float(payload.get("distance_km", 0))
    liters = round(distance_km * 0.28, 2)
    return {"ok": True, "request_id": str(uuid4()), "trip_id": trip_id, "liters": liters, "method": "integration_hub"}
