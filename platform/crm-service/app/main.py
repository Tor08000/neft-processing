from __future__ import annotations

from typing import Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

SERVICE_NAME = "crm-service"
SERVICE_VERSION = "stub-v0"
METRIC_PREFIX = "crm_service"

app = FastAPI(title="CRM Service Stub")

CRM_SERVICE_UP = Gauge(f"{METRIC_PREFIX}_up", "CRM stub service up")
CRM_SERVICE_HTTP_REQUESTS_TOTAL = Counter(
    f"{METRIC_PREFIX}_http_requests_total",
    "Total HTTP requests handled by CRM stub",
    ["method", "path", "status"],
)

CRM_SERVICE_UP.set(1)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next: Callable[[Request], Response]) -> Response:
    try:
        response = await call_next(request)
    except Exception:
        CRM_SERVICE_HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            path=request.url.path,
            status="500",
        ).inc()
        raise

    CRM_SERVICE_HTTP_REQUESTS_TOTAL.labels(
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
