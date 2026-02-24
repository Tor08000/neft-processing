from __future__ import annotations

import logging
import os
import time
from typing import Callable

from fastapi import FastAPI, Header, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from neft_logistics_service.compute.deviation import compute_deviation
from neft_logistics_service.compute.eta import compute_eta
from neft_logistics_service.compute.explain import explain_deviation, explain_eta
from neft_logistics_service.providers import get_provider
from neft_logistics_service.schemas import (
    DeviationRequest,
    DeviationResponse,
    EtaRequest,
    EtaResponse,
    ExplainRequest,
    ExplainResponse,
)
from neft_logistics_service.schemas.fleet import FleetListRequest, FleetListResponse, FleetUpsertRequest, FleetUpsertResponse
from neft_logistics_service.schemas.fuel import FuelConsumptionRequest, FuelConsumptionResponse
from neft_logistics_service.schemas.trips import TripCreateRequest, TripCreateResponse, TripStatusResponse
from neft_logistics_service.settings import get_settings
from neft_logistics_service.storage.idempotency import IdempotencyStore, hash_payload

settings = get_settings()
logger = logging.getLogger(__name__)
idempotency_store = IdempotencyStore(settings.idempotency_db_path)

app = FastAPI(title="Logistics Service", version=settings.service_version)

LOGISTICS_COMPUTE_TOTAL = Counter(
    "logistics_compute_total",
    "Total compute calls for logistics-service",
    ["type", "status"],
)
LOGISTICS_COMPUTE_DURATION = Histogram(
    "logistics_compute_duration_seconds",
    "Latency of compute operations in logistics-service",
)
LOGISTICS_PROVIDER_ERRORS_TOTAL = Counter(
    "logistics_provider_errors_total",
    "Provider failures inside logistics-service",
    ["provider", "type"],
)

for compute_type in ("eta", "deviation"):
    for status in ("success", "error"):
        LOGISTICS_COMPUTE_TOTAL.labels(type=compute_type, status=status).inc(0)
    LOGISTICS_PROVIDER_ERRORS_TOTAL.labels(provider=settings.provider, type=compute_type).inc(0)
LOGISTICS_COMPUTE_DURATION.observe(0.0)


@app.on_event("startup")
def startup_log_mode() -> None:
    app_env = (settings.app_env or "").strip().lower()
    allow_override = os.getenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "0").strip() == "1"
    provider_mode = (settings.provider or "").strip().lower()
    if app_env in {"prod", "production"} and provider_mode in {"mock", "stub"} and not allow_override:
        raise RuntimeError(
            "prod guardrail violation: LOGISTICS_PROVIDER is mock/stub in prod. "
            "Use ALLOW_MOCK_PROVIDERS_IN_PROD=1 only for explicit override."
        )
    logger.info(
        "running in %s mode",
        settings.app_env.upper(),
        extra={
            "app_env": settings.app_env,
            "use_mock_logistics": settings.use_mock_logistics,
            "provider": settings.provider,
        },
    )


@app.middleware("http")
async def metrics_middleware(request: Request, call_next: Callable[[Request], Response]) -> Response:
    return await call_next(request)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.service_version,
    }


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/eta", response_model=EtaResponse)
def eta_endpoint(payload: EtaRequest) -> EtaResponse:
    provider = get_provider(settings.provider)
    start = time.monotonic()
    try:
        response = compute_eta(payload, provider)
        LOGISTICS_COMPUTE_TOTAL.labels(type="eta", status="success").inc()
        return response
    except Exception as exc:  # noqa: BLE001
        LOGISTICS_PROVIDER_ERRORS_TOTAL.labels(provider=provider.name, type="eta").inc()
        LOGISTICS_COMPUTE_TOTAL.labels(type="eta", status="error").inc()
        raise HTTPException(status_code=502, detail="provider_error") from exc
    finally:
        LOGISTICS_COMPUTE_DURATION.observe(time.monotonic() - start)


@app.post("/v1/deviation", response_model=DeviationResponse)
def deviation_endpoint(payload: DeviationRequest) -> DeviationResponse:
    provider = get_provider(settings.provider)
    start = time.monotonic()
    try:
        response = compute_deviation(payload, provider)
        LOGISTICS_COMPUTE_TOTAL.labels(type="deviation", status="success").inc()
        return response
    except Exception as exc:  # noqa: BLE001
        LOGISTICS_PROVIDER_ERRORS_TOTAL.labels(provider=provider.name, type="deviation").inc()
        LOGISTICS_COMPUTE_TOTAL.labels(type="deviation", status="error").inc()
        raise HTTPException(status_code=502, detail="provider_error") from exc
    finally:
        LOGISTICS_COMPUTE_DURATION.observe(time.monotonic() - start)


@app.post("/v1/explain", response_model=ExplainResponse)
def explain_endpoint(payload: ExplainRequest) -> ExplainResponse:
    provider = get_provider(settings.provider)
    if payload.kind == "eta":
        explain = explain_eta(
            EtaRequest(
                route_id="explain",
                points=[],
                vehicle={"type": "truck", "fuel_type": "diesel"},
                context=payload.context,
            ),
            provider,
        )
        return ExplainResponse(explain=explain)
    if payload.kind == "deviation":
        explain = explain_deviation(
            DeviationRequest(
                route_id="explain",
                planned_polyline=[(0.0, 0.0), (0.0, 0.0)],
                actual_point={"lat": 0.0, "lon": 0.0},
                threshold_meters=0,
            ),
            provider,
        )
        return ExplainResponse(explain=explain)
    raise HTTPException(status_code=400, detail="unsupported_explain_kind")


@app.post("/v1/fleet/list", response_model=FleetListResponse)
def fleet_list_endpoint(payload: FleetListRequest) -> FleetListResponse:
    provider = get_provider(settings.provider)
    return provider.fleet_list(payload)


@app.post("/v1/fleet/upsert", response_model=FleetUpsertResponse)
def fleet_upsert_endpoint(payload: FleetUpsertRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> FleetUpsertResponse:
    provider = get_provider(settings.provider)
    if not idempotency_key:
        response = provider.fleet_upsert(payload)
        response.idempotency_status = "new"
        return response

    scope = "fleet_upsert"
    req_hash = hash_payload(payload.model_dump(mode="json"))
    existing = idempotency_store.get(scope, idempotency_key)
    if existing:
        if existing.status == "processing":
            raise HTTPException(status_code=409, detail="idempotency_processing")
        if existing.response_body is not None:
            replay = dict(existing.response_body)
            replay["idempotency_key"] = idempotency_key
            replay["idempotency_status"] = "replayed"
            return FleetUpsertResponse(**replay)
    if not idempotency_store.start_processing(scope, idempotency_key, req_hash):
        raise HTTPException(status_code=409, detail="idempotency_processing")
    response = provider.fleet_upsert(payload)
    body = response.model_dump(mode="json")
    idempotency_store.finalize(scope, idempotency_key, "success", 200, body)
    response.idempotency_key = idempotency_key
    response.idempotency_status = "new"
    return response


@app.post("/v1/trips/create", response_model=TripCreateResponse)
def trip_create_endpoint(payload: TripCreateRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> TripCreateResponse:
    provider = get_provider(settings.provider)
    if not idempotency_key:
        response = provider.trip_create(payload)
        response.idempotency_status = "new"
        return response

    scope = "trip_create"
    req_hash = hash_payload(payload.model_dump(mode="json"))
    existing = idempotency_store.get(scope, idempotency_key)
    if existing:
        if existing.status == "processing":
            raise HTTPException(status_code=409, detail="idempotency_processing")
        if existing.response_body is not None:
            replay = dict(existing.response_body)
            replay["idempotency_key"] = idempotency_key
            replay["idempotency_status"] = "replayed"
            return TripCreateResponse(**replay)
    if not idempotency_store.start_processing(scope, idempotency_key, req_hash):
        raise HTTPException(status_code=409, detail="idempotency_processing")
    response = provider.trip_create(payload)
    body = response.model_dump(mode="json")
    idempotency_store.finalize(scope, idempotency_key, "success", 200, body)
    response.idempotency_key = idempotency_key
    response.idempotency_status = "new"
    return response


@app.get("/v1/trips/{trip_id}/status", response_model=TripStatusResponse)
def trip_status_endpoint(trip_id: str) -> TripStatusResponse:
    provider = get_provider(settings.provider)
    return provider.trip_get_status(trip_id)


@app.post("/v1/fuel/consumption", response_model=FuelConsumptionResponse)
def fuel_consumption_endpoint(payload: FuelConsumptionRequest) -> FuelConsumptionResponse:
    provider = get_provider(settings.provider)
    return provider.fuel_get_consumption(payload)
