from __future__ import annotations

import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest

METRICS_REGISTRY = CollectorRegistry()

AUTH_HOST_UP = Gauge("auth_host_up", "Auth host service up", registry=METRICS_REGISTRY)
AUTH_HOST_HTTP_REQUESTS_TOTAL = Counter(
    "auth_host_http_requests_total",
    "Total HTTP requests handled by auth-host",
    ["method", "path", "status"],
    registry=METRICS_REGISTRY,
)
AUTH_HOST_HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "auth_host_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    registry=METRICS_REGISTRY,
)

AUTH_HOST_UP.set(1)


async def metrics_middleware(request: Request, call_next: Callable[[Request], Response]) -> Response:
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        AUTH_HOST_HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            path=request.url.path,
            status="500",
        ).inc()
        raise
    finally:
        duration = time.perf_counter() - start_time
        AUTH_HOST_HTTP_REQUEST_DURATION_SECONDS.labels(
            method=request.method,
            path=request.url.path,
        ).observe(duration)

    AUTH_HOST_HTTP_REQUESTS_TOTAL.labels(
        method=request.method,
        path=request.url.path,
        status=str(response.status_code),
    ).inc()
    return response


def metrics_response() -> Response:
    payload = generate_latest(METRICS_REGISTRY)
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
