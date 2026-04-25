from __future__ import annotations

from typing import Callable

from fastapi import FastAPI, Request, Response

from app.db import Base, engine
from app.metrics_compat import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from app.models import *  # noqa: F403
from app.routers import audit, comments, contacts, deals, pipelines, tasks

# Compatibility/shadow CRM surface:
# - canonical CRM control plane owner lives in processing-core admin CRM
# - this service still serves /api/v1/crm/* tails until external consumers are explicitly retired
SERVICE_NAME = "crm-service"
SERVICE_VERSION = "v1.0.0"
METRIC_PREFIX = "crm_service"

app = FastAPI(title="NEFT CRM Service", version=SERVICE_VERSION)
Base.metadata.create_all(bind=engine)

CRM_SERVICE_UP = Gauge(f"{METRIC_PREFIX}_up", "CRM service up")
CRM_SERVICE_HTTP_REQUESTS_TOTAL = Counter(
    f"{METRIC_PREFIX}_http_requests_total", "Total HTTP requests handled by CRM", ["method", "path", "status"]
)
CRM_SERVICE_UP.set(1)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next: Callable[[Request], Response]) -> Response:
    try:
        response = await call_next(request)
    except Exception:
        CRM_SERVICE_HTTP_REQUESTS_TOTAL.labels(method=request.method, path=request.url.path, status="500").inc()
        raise
    CRM_SERVICE_HTTP_REQUESTS_TOTAL.labels(method=request.method, path=request.url.path, status=str(response.status_code)).inc()
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(contacts.router, prefix="/api/v1/crm")
app.include_router(pipelines.router, prefix="/api/v1/crm")
app.include_router(deals.router, prefix="/api/v1/crm")
app.include_router(tasks.router, prefix="/api/v1/crm")
app.include_router(comments.router, prefix="/api/v1/crm")
app.include_router(audit.router, prefix="/api/v1/crm")
