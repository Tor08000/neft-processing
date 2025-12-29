from __future__ import annotations

import hashlib
import logging
import time
from datetime import date
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from app.renderer import HtmlRenderer
from app.schemas import PresignRequest, PresignResponse, RenderRequest, RenderResponse
from app.settings import get_settings
from app.storage import S3Storage

settings = get_settings()
logger = logging.getLogger(__name__)

SERVICE_NAME = settings.service_name
SERVICE_VERSION = settings.service_version
METRIC_PREFIX = "document_service"

app = FastAPI(title="Document Service")

DOCUMENT_SERVICE_UP = Gauge(f"{METRIC_PREFIX}_up", "Document service up")
DOCUMENT_SERVICE_HTTP_REQUESTS_TOTAL = Counter(
    f"{METRIC_PREFIX}_http_requests_total",
    "Total HTTP requests handled by document service",
    ["method", "path", "status"],
)
DOCUMENT_SERVICE_RENDER_TOTAL = Counter(
    f"{METRIC_PREFIX}_render_total",
    "Total render attempts",
    ["status"],
)
DOCUMENT_SERVICE_RENDER_DURATION_SECONDS = Histogram(
    f"{METRIC_PREFIX}_render_duration_seconds",
    "Duration of render requests in seconds",
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30),
)
DOCUMENT_SERVICE_S3_UPLOAD_ERRORS_TOTAL = Counter(
    f"{METRIC_PREFIX}_s3_upload_errors_total",
    "S3 upload failures",
)

DOCUMENT_SERVICE_UP.set(1)


def get_storage() -> S3Storage:
    return S3Storage()


def get_renderer() -> HtmlRenderer:
    return HtmlRenderer()


@app.middleware("http")
async def metrics_middleware(request: Request, call_next: Callable[[Request], Response]) -> Response:
    try:
        response = await call_next(request)
    except Exception:
        DOCUMENT_SERVICE_HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            path=request.url.path,
            status="500",
        ).inc()
        raise

    DOCUMENT_SERVICE_HTTP_REQUESTS_TOTAL.labels(
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


@app.post("/v1/render", response_model=RenderResponse)
def render_document(
    payload: RenderRequest,
    request: Request,
    storage: S3Storage = Depends(get_storage),
    renderer: HtmlRenderer = Depends(get_renderer),
) -> RenderResponse:
    start = time.monotonic()
    request_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")

    if payload.template_kind.upper() != "HTML":
        raise HTTPException(status_code=422, detail="unsupported_template_kind")
    if payload.output_format.upper() != "PDF":
        raise HTTPException(status_code=422, detail="unsupported_output_format")

    document_date = payload.document_date or date.today()
    object_key = _build_object_key(
        tenant_id=payload.tenant_id,
        doc_type=payload.doc_type,
        doc_id=payload.doc_id,
        version=payload.version,
        document_date=document_date,
    )

    existing = storage.head_object(object_key)
    if existing:
        sha256 = existing.sha256
        if not sha256:
            payload_bytes = storage.get_bytes(object_key)
            if payload_bytes is None:
                existing = None
            else:
                sha256 = hashlib.sha256(payload_bytes).hexdigest()
        if existing:
            DOCUMENT_SERVICE_RENDER_TOTAL.labels(status="success").inc()
            DOCUMENT_SERVICE_RENDER_DURATION_SECONDS.observe(time.monotonic() - start)
            logger.info(
                "document_service.render_cached",
                extra={
                    "request_id": request_id,
                    "doc_id": payload.doc_id,
                    "doc_type": payload.doc_type,
                    "object_key": object_key,
                    "duration_ms": int((time.monotonic() - start) * 1000),
                    "sha256": (sha256 or "")[:8],
                },
            )
            return RenderResponse(
                bucket=existing.bucket,
                object_key=existing.object_key,
                sha256=sha256 or "",
                size_bytes=existing.size_bytes,
                content_type=existing.content_type,
                version=payload.version,
            )

    try:
        render_result = renderer.render(payload.template_html, payload.data)
        pdf_bytes = render_result.pdf_bytes
        sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        storage.ensure_bucket()
        storage.put_bytes(
            object_key,
            pdf_bytes,
            content_type="application/pdf",
            metadata={"sha256": sha256, "version": str(payload.version)},
        )
    except Exception as exc:
        DOCUMENT_SERVICE_RENDER_TOTAL.labels(status="fail").inc()
        DOCUMENT_SERVICE_S3_UPLOAD_ERRORS_TOTAL.inc()
        logger.exception(
            "document_service.render_failed",
            extra={
                "request_id": request_id,
                "doc_id": payload.doc_id,
                "doc_type": payload.doc_type,
                "error": str(exc),
            },
        )
        raise HTTPException(status_code=500, detail="render_failed") from exc

    duration = time.monotonic() - start
    DOCUMENT_SERVICE_RENDER_TOTAL.labels(status="success").inc()
    DOCUMENT_SERVICE_RENDER_DURATION_SECONDS.observe(duration)
    logger.info(
        "document_service.rendered",
        extra={
            "request_id": request_id,
            "doc_id": payload.doc_id,
            "doc_type": payload.doc_type,
            "duration_ms": int(duration * 1000),
            "sha256": sha256[:8],
        },
    )

    return RenderResponse(
        bucket=storage.bucket,
        object_key=object_key,
        sha256=sha256,
        size_bytes=len(pdf_bytes),
        content_type="application/pdf",
        version=payload.version,
    )


@app.post("/v1/presign", response_model=PresignResponse)
def presign_download(payload: PresignRequest) -> PresignResponse:
    storage = S3Storage(bucket=payload.bucket)
    url = storage.presign(payload.object_key, ttl_seconds=payload.ttl_seconds)
    if not url:
        raise HTTPException(status_code=500, detail="presign_failed")
    return PresignResponse(url=url)


def _build_object_key(
    *,
    tenant_id: int,
    doc_type: str,
    doc_id: str,
    version: int,
    document_date: date,
) -> str:
    return (
        f"documents/tenant-{tenant_id}/{doc_type}/{document_date:%Y}/{document_date:%m}/"
        f"{doc_id}/v{version}.pdf"
    )
