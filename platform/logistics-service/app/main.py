from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.compute.deviation import compute_deviation
from app.compute.eta import compute_eta
from app.compute.explain import explain_deviation, explain_eta
from app.providers import get_provider
from app.schemas import (
    DeviationRequest,
    DeviationResponse,
    EtaRequest,
    EtaResponse,
    ExplainRequest,
    ExplainResponse,
)
from app.settings import get_settings

settings = get_settings()

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
