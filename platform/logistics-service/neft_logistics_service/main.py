from __future__ import annotations

import logging
import os
import time
from typing import Callable, TypeVar

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from neft_logistics_service.compute.deviation import compute_deviation
from neft_logistics_service.compute.eta import compute_eta
from neft_logistics_service.compute.explain import explain_deviation, explain_eta
from neft_logistics_service.compute.preview import preview_route
from neft_logistics_service.providers import get_compute_provider, get_provider
from neft_logistics_service.providers.base import ProviderUnavailableError
from neft_logistics_service.schemas import (
    DeviationRequest,
    DeviationResponse,
    EtaRequest,
    EtaResponse,
    ExplainRequest,
    ExplainResponse,
    RoutePreviewRequest,
    RoutePreviewResponse,
)
from neft_logistics_service.schemas.fleet import FleetListRequest, FleetListResponse, FleetUpsertRequest, FleetUpsertResponse
from neft_logistics_service.schemas.fuel import FuelConsumptionRequest, FuelConsumptionResponse
from neft_logistics_service.schemas.trips import TripCreateRequest, TripCreateResponse, TripStatusResponse
from neft_logistics_service.settings import get_settings
from neft_logistics_service.storage.idempotency import IdempotencyStore, hash_payload

settings = get_settings()
logger = logging.getLogger(__name__)
idempotency_store = IdempotencyStore(settings.idempotency_db_path)
T = TypeVar("T")

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
    LOGISTICS_PROVIDER_ERRORS_TOTAL.labels(provider=settings.compute_provider, type=compute_type).inc(0)
LOGISTICS_COMPUTE_DURATION.observe(0.0)


def _provider_mode(value: str | None, default: str = "disabled") -> str:
    mode = (value or default).strip().lower()
    if mode in {"prod", "real"}:
        return "production"
    return mode or default


def _provider_health(
    *,
    provider: str,
    mode: str,
    status: str,
    configured: bool,
    message: str,
    last_error_code: str | None = None,
) -> dict[str, object]:
    return {
        "service": settings.service_name,
        "provider": provider,
        "mode": mode,
        "status": status,
        "configured": configured,
        "last_success_at": None,
        "last_error_code": last_error_code,
        "message": message,
    }


def _provider_unavailable_detail(exc: ProviderUnavailableError) -> dict[str, object]:
    return {
        "category": "provider_unavailable",
        "error": exc.code,
        "provider": exc.provider,
        "mode": exc.mode,
        "retryable": False,
    }


def _raise_provider_unavailable(exc: ProviderUnavailableError) -> None:
    raise HTTPException(status_code=503, detail=_provider_unavailable_detail(exc)) from exc


def _run_transport_call(provider_name: str, op: str, callback: Callable[[], T]) -> T:
    try:
        return callback()
    except ProviderUnavailableError as exc:
        LOGISTICS_PROVIDER_ERRORS_TOTAL.labels(provider=exc.provider, type=op).inc()
        _raise_provider_unavailable(exc)
    except Exception as exc:  # noqa: BLE001
        LOGISTICS_PROVIDER_ERRORS_TOTAL.labels(provider=provider_name, type=op).inc()
        raise HTTPException(
            status_code=502,
            detail={
                "category": "provider_error",
                "error": "provider_error",
                "provider": provider_name,
                "retryable": True,
            },
        ) from exc


def _external_provider_health() -> list[dict[str, object]]:
    transport_mode = _provider_mode(settings.provider, "integration_hub")
    compute_mode = _provider_mode(settings.compute_provider, "osrm")
    transport_supported = transport_mode in {"mock", "stub", "integration_hub", "disabled", "degraded"}
    compute_supported = compute_mode in {"mock", "stub", "osrm", "disabled", "degraded"}
    transport_configured = transport_mode == "integration_hub" and bool((settings.integration_hub_base_url or "").strip())
    compute_configured = compute_mode == "osrm" and bool((settings.osrm_base_url or "").strip())
    if not transport_supported:
        transport_status = "UNSUPPORTED"
    elif transport_mode in {"mock", "stub"}:
        transport_status = "CONFIGURED"
    elif transport_mode == "integration_hub":
        transport_status = "CONFIGURED" if transport_configured else "DEGRADED"
    else:
        transport_status = "DISABLED" if transport_mode == "disabled" else "DEGRADED"

    if not compute_supported:
        compute_status = "UNSUPPORTED"
    elif compute_mode in {"mock", "stub"}:
        compute_status = "CONFIGURED"
    elif compute_mode == "osrm":
        compute_status = "CONFIGURED" if compute_configured else "DEGRADED"
    else:
        compute_status = "DISABLED" if compute_mode == "disabled" else "DEGRADED"

    return [
        _provider_health(
            provider="logistics_transport",
            mode=transport_mode,
            status=transport_status,
            configured=transport_configured or transport_mode in {"mock", "stub"},
            last_error_code=None if transport_status in {"CONFIGURED", "DISABLED"} else "logistics_transport_not_configured",
            message="Logistics transport adapter is configured" if transport_status == "CONFIGURED" else "Logistics write transport remains provider-gated",
        ),
        _provider_health(
            provider="osrm_route_compute",
            mode=compute_mode,
            status=compute_status,
            configured=compute_configured or compute_mode in {"mock", "stub"},
            last_error_code=None if compute_status in {"CONFIGURED", "DISABLED"} else "osrm_not_configured",
            message="OSRM route compute adapter is configured" if compute_status == "CONFIGURED" else "Route compute requires OSRM_BASE_URL before provider smoke can pass",
        ),
    ]


@app.on_event("startup")
def startup_log_mode() -> None:
    app_env = (settings.app_env or "").strip().lower()
    allow_override = os.getenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "0").strip() == "1"
    transport_provider_mode = (settings.provider or "").strip().lower()
    compute_provider_mode = (settings.compute_provider or "").strip().lower()
    if app_env in {"prod", "production"} and transport_provider_mode in {"mock", "stub"} and not allow_override:
        raise RuntimeError(
            "prod guardrail violation: LOGISTICS_PROVIDER is mock/stub in prod. "
            "Use ALLOW_MOCK_PROVIDERS_IN_PROD=1 only for explicit override."
        )
    if app_env in {"prod", "production"} and compute_provider_mode in {"mock", "stub"} and not allow_override:
        raise RuntimeError(
            "prod guardrail violation: LOGISTICS_COMPUTE_PROVIDER is mock/stub in prod. "
            "Use ALLOW_MOCK_PROVIDERS_IN_PROD=1 only for explicit override."
        )
    try:
        get_provider(settings.provider)
        get_compute_provider(settings.compute_provider)
    except ValueError as exc:
        raise RuntimeError(f"logistics_provider_misconfigured:{exc}") from exc
    logger.info(
        "running in %s mode",
        settings.app_env.upper(),
        extra={
            "app_env": settings.app_env,
            "use_mock_logistics": settings.use_mock_logistics,
            "provider": settings.provider,
            "compute_provider": settings.compute_provider,
        },
    )


@app.middleware("http")
async def metrics_middleware(request: Request, call_next: Callable[[Request], Response]) -> Response:
    return await call_next(request)


@app.get("/health")
def health() -> dict:
    external_providers = _external_provider_health()
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.service_version,
        "provider_modes": {
            "transport": _provider_mode(settings.provider, "integration_hub"),
            "compute": _provider_mode(settings.compute_provider, "osrm"),
        },
        "external_providers": external_providers,
        "providers": external_providers,
    }


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/eta", response_model=EtaResponse)
def eta_endpoint(payload: EtaRequest) -> EtaResponse:
    provider = get_compute_provider(settings.compute_provider)
    start = time.monotonic()
    try:
        response = compute_eta(payload, provider)
        LOGISTICS_COMPUTE_TOTAL.labels(type="eta", status="success").inc()
        return response
    except ProviderUnavailableError as exc:
        LOGISTICS_PROVIDER_ERRORS_TOTAL.labels(provider=exc.provider, type="eta").inc()
        LOGISTICS_COMPUTE_TOTAL.labels(type="eta", status="error").inc()
        _raise_provider_unavailable(exc)
    except Exception as exc:  # noqa: BLE001
        LOGISTICS_PROVIDER_ERRORS_TOTAL.labels(provider=provider.name, type="eta").inc()
        LOGISTICS_COMPUTE_TOTAL.labels(type="eta", status="error").inc()
        raise HTTPException(status_code=502, detail="provider_error") from exc
    finally:
        LOGISTICS_COMPUTE_DURATION.observe(time.monotonic() - start)


@app.post("/v1/deviation", response_model=DeviationResponse)
def deviation_endpoint(payload: DeviationRequest) -> DeviationResponse:
    provider = get_compute_provider(settings.compute_provider)
    start = time.monotonic()
    try:
        response = compute_deviation(payload, provider)
        LOGISTICS_COMPUTE_TOTAL.labels(type="deviation", status="success").inc()
        return response
    except ProviderUnavailableError as exc:
        LOGISTICS_PROVIDER_ERRORS_TOTAL.labels(provider=exc.provider, type="deviation").inc()
        LOGISTICS_COMPUTE_TOTAL.labels(type="deviation", status="error").inc()
        _raise_provider_unavailable(exc)
    except Exception as exc:  # noqa: BLE001
        LOGISTICS_PROVIDER_ERRORS_TOTAL.labels(provider=provider.name, type="deviation").inc()
        LOGISTICS_COMPUTE_TOTAL.labels(type="deviation", status="error").inc()
        raise HTTPException(status_code=502, detail="provider_error") from exc
    finally:
        LOGISTICS_COMPUTE_DURATION.observe(time.monotonic() - start)


@app.post("/v1/explain", response_model=ExplainResponse)
def explain_endpoint(payload: ExplainRequest) -> ExplainResponse:
    provider = get_compute_provider(settings.compute_provider)
    if payload.kind == "eta":
        try:
            explain = explain_eta(
                EtaRequest(
                    route_id="explain",
                    points=[],
                    vehicle={"type": "truck", "fuel_type": "diesel"},
                    context=payload.context,
                ),
                provider,
            )
        except ProviderUnavailableError as exc:
            _raise_provider_unavailable(exc)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail="provider_error") from exc
        return ExplainResponse(provider=provider.name, explain=explain)
    if payload.kind == "deviation":
        try:
            explain = explain_deviation(
                DeviationRequest(
                    route_id="explain",
                    planned_polyline=[(0.0, 0.0), (0.0, 0.0)],
                    actual_point={"lat": 0.0, "lon": 0.0},
                    threshold_meters=0,
                ),
                provider,
            )
        except ProviderUnavailableError as exc:
            _raise_provider_unavailable(exc)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail="provider_error") from exc
        return ExplainResponse(provider=provider.name, explain=explain)
    raise HTTPException(status_code=400, detail="unsupported_explain_kind")


def _require_internal_token(x_internal_token: str | None = Header(default=None, alias="X-Internal-Token")) -> None:
    if settings.internal_token and x_internal_token != settings.internal_token:
        raise HTTPException(status_code=401, detail="invalid_internal_token")


@app.post("/api/int/v1/routes/preview", response_model=RoutePreviewResponse)
def route_preview_endpoint(
    payload: RoutePreviewRequest,
    _auth: None = Depends(_require_internal_token),
) -> RoutePreviewResponse:
    provider = get_compute_provider(settings.compute_provider)
    try:
        return preview_route(payload, provider)
    except ProviderUnavailableError as exc:
        _raise_provider_unavailable(exc)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="provider_error") from exc


@app.post("/v1/fleet/list", response_model=FleetListResponse)
def fleet_list_endpoint(payload: FleetListRequest) -> FleetListResponse:
    provider = get_provider(settings.provider)
    return _run_transport_call(provider.name, "fleet_list", lambda: provider.fleet_list(payload))


@app.post("/v1/fleet/upsert", response_model=FleetUpsertResponse)
def fleet_upsert_endpoint(payload: FleetUpsertRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> FleetUpsertResponse:
    provider = get_provider(settings.provider)
    if not idempotency_key:
        response = _run_transport_call(provider.name, "fleet_upsert", lambda: provider.fleet_upsert(payload))
        response.idempotency_status = "new"
        return response

    scope = "fleet_upsert"
    req_hash = hash_payload(payload.model_dump(mode="json"))
    existing = idempotency_store.get(scope, idempotency_key)
    if existing:
        if existing.status == "processing":
            raise HTTPException(status_code=409, detail="idempotency_processing")
        if existing.status == "error" and existing.response_body is not None:
            raise HTTPException(status_code=existing.response_code or 503, detail=existing.response_body)
        if existing.response_body is not None:
            replay = dict(existing.response_body)
            replay["idempotency_key"] = idempotency_key
            replay["idempotency_status"] = "replayed"
            return FleetUpsertResponse(**replay)
    if not idempotency_store.start_processing(scope, idempotency_key, req_hash):
        raise HTTPException(status_code=409, detail="idempotency_processing")
    try:
        response = _run_transport_call(provider.name, "fleet_upsert", lambda: provider.fleet_upsert(payload))
    except HTTPException as exc:
        if isinstance(exc.detail, dict):
            idempotency_store.finalize(scope, idempotency_key, "error", exc.status_code, exc.detail)
        raise
    body = response.model_dump(mode="json")
    idempotency_store.finalize(scope, idempotency_key, "success", 200, body)
    response.idempotency_key = idempotency_key
    response.idempotency_status = "new"
    return response


@app.post("/v1/trips/create", response_model=TripCreateResponse)
def trip_create_endpoint(payload: TripCreateRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> TripCreateResponse:
    provider = get_provider(settings.provider)
    if not idempotency_key:
        response = _run_transport_call(provider.name, "trip_create", lambda: provider.trip_create(payload))
        response.idempotency_status = "new"
        return response

    scope = "trip_create"
    req_hash = hash_payload(payload.model_dump(mode="json"))
    existing = idempotency_store.get(scope, idempotency_key)
    if existing:
        if existing.status == "processing":
            raise HTTPException(status_code=409, detail="idempotency_processing")
        if existing.status == "error" and existing.response_body is not None:
            raise HTTPException(status_code=existing.response_code or 503, detail=existing.response_body)
        if existing.response_body is not None:
            replay = dict(existing.response_body)
            replay["idempotency_key"] = idempotency_key
            replay["idempotency_status"] = "replayed"
            return TripCreateResponse(**replay)
    if not idempotency_store.start_processing(scope, idempotency_key, req_hash):
        raise HTTPException(status_code=409, detail="idempotency_processing")
    try:
        response = _run_transport_call(provider.name, "trip_create", lambda: provider.trip_create(payload))
    except HTTPException as exc:
        if isinstance(exc.detail, dict):
            idempotency_store.finalize(scope, idempotency_key, "error", exc.status_code, exc.detail)
        raise
    body = response.model_dump(mode="json")
    idempotency_store.finalize(scope, idempotency_key, "success", 200, body)
    response.idempotency_key = idempotency_key
    response.idempotency_status = "new"
    return response


@app.get("/v1/trips/{trip_id}/status", response_model=TripStatusResponse)
def trip_status_endpoint(trip_id: str) -> TripStatusResponse:
    provider = get_provider(settings.provider)
    return _run_transport_call(provider.name, "trip_get_status", lambda: provider.trip_get_status(trip_id))


@app.post("/v1/fuel/consumption", response_model=FuelConsumptionResponse)
def fuel_consumption_endpoint(
    payload: FuelConsumptionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> FuelConsumptionResponse:
    provider = get_provider(settings.provider)
    if not idempotency_key:
        response = _run_transport_call(provider.name, "fuel_consumption", lambda: provider.fuel_get_consumption(payload))
        response.idempotency_status = "new"
        return response

    scope = "fuel_consumption"
    req_hash = hash_payload(payload.model_dump(mode="json"))
    existing = idempotency_store.get(scope, idempotency_key)
    if existing:
        if existing.status == "processing":
            raise HTTPException(status_code=409, detail="idempotency_processing")
        if existing.status == "error" and existing.response_body is not None:
            raise HTTPException(status_code=existing.response_code or 503, detail=existing.response_body)
        if existing.response_body is not None:
            replay = dict(existing.response_body)
            replay["idempotency_key"] = idempotency_key
            replay["idempotency_status"] = "replayed"
            return FuelConsumptionResponse(**replay)
    if not idempotency_store.start_processing(scope, idempotency_key, req_hash):
        raise HTTPException(status_code=409, detail="idempotency_processing")
    try:
        provider_payload = payload.model_copy(update={"idempotency_key": idempotency_key})
        response = _run_transport_call(provider.name, "fuel_consumption", lambda: provider.fuel_get_consumption(provider_payload))
    except HTTPException as exc:
        if isinstance(exc.detail, dict):
            idempotency_store.finalize(scope, idempotency_key, "error", exc.status_code, exc.detail)
        raise
    body = response.model_dump(mode="json")
    idempotency_store.finalize(scope, idempotency_key, "success", 200, body)
    response.idempotency_key = idempotency_key
    response.idempotency_status = "new"
    return response
