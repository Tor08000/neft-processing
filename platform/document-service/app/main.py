from __future__ import annotations

import hashlib
import logging
import time
from datetime import date
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from jsonschema import ValidationError, validate
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from app.renderer import HtmlRenderer
from app.schemas import (
    PresignRequest,
    PresignResponse,
    RenderRequest,
    RenderResponse,
    SignRequest,
    SignResponse,
    TemplateDetail,
    TemplateListItem,
    VerifyRequest,
    VerifyResponse,
)
from app.sign.registry import ProviderRegistry, get_registry
from app.settings import get_settings
from app.storage import S3Storage
from app.templates import TemplateRegistry

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
DOCUMENT_SERVICE_SIGN_TOTAL = Counter(
    f"{METRIC_PREFIX}_sign_total",
    "Total sign attempts",
    ["status"],
)
DOCUMENT_SERVICE_SIGN_DURATION_SECONDS = Histogram(
    f"{METRIC_PREFIX}_sign_duration_seconds",
    "Duration of sign requests in seconds",
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30),
)
DOCUMENT_SERVICE_SIGN_ERRORS_TOTAL = Counter(
    f"{METRIC_PREFIX}_sign_errors_total",
    "Signing failures by error code",
    ["code"],
)
DOCUMENT_SERVICE_VERIFY_TOTAL = Counter(
    f"{METRIC_PREFIX}_verify_total",
    "Total verify attempts",
    ["status"],
)

DOCUMENT_SERVICE_UP.set(1)


def get_storage() -> S3Storage:
    return S3Storage()


def get_renderer() -> HtmlRenderer:
    return HtmlRenderer()


def get_sign_registry() -> ProviderRegistry:
    return get_registry()


def get_template_registry() -> TemplateRegistry:
    return TemplateRegistry()


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
    templates: TemplateRegistry = Depends(get_template_registry),
) -> RenderResponse:
    start = time.monotonic()
    request_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")

    template_html = payload.template_html
    render_data = payload.data or {}
    schema_hash = None
    template_hash = None

    if payload.template_code:
        definition = templates.get_template(payload.template_code)
        if not definition:
            raise HTTPException(status_code=404, detail="template_not_found")
        template_html = definition.load_template()
        render_data = payload.variables or {}
        schema = definition.load_schema()
        try:
            validate(instance=render_data, schema=schema)
        except ValidationError as exc:
            error_path = ".".join([str(item) for item in exc.path]) if exc.path else "variables"
            raise HTTPException(
                status_code=400,
                detail={"error": "schema_validation_failed", "field": error_path, "message": exc.message},
            ) from exc
        template_hash = definition.template_hash()
        schema_hash = definition.schema_hash()
        template_kind = definition.engine
    else:
        template_kind = payload.template_kind

    if not template_html or not template_kind or template_kind.upper() != "HTML":
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
                template_hash=template_hash,
                schema_hash=schema_hash,
            )

    try:
        render_result = renderer.render(template_html, render_data)
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
        template_hash=template_hash,
        schema_hash=schema_hash,
    )


@app.get("/v1/templates", response_model=list[TemplateListItem])
def list_templates(templates: TemplateRegistry = Depends(get_template_registry)) -> list[TemplateListItem]:
    response: list[TemplateListItem] = []
    for template in templates.list_templates():
        repo_path, schema_path = templates.repo_paths(template)
        response.append(
            TemplateListItem(
                code=template.code,
                title=template.title,
                engine=template.engine,
                repo_path=repo_path,
                schema_path=schema_path,
                template_hash=template.template_hash(),
                schema_hash=template.schema_hash(),
                version=template.version,
                status=template.status,
            )
        )
    return response


@app.get("/v1/templates/{code}", response_model=TemplateDetail)
def get_template(code: str, templates: TemplateRegistry = Depends(get_template_registry)) -> TemplateDetail:
    template = templates.get_template(code)
    if not template:
        raise HTTPException(status_code=404, detail="template_not_found")
    repo_path, schema_path = templates.repo_paths(template)
    return TemplateDetail(
        code=template.code,
        title=template.title,
        engine=template.engine,
        repo_path=repo_path,
        schema_path=schema_path,
        template_hash=template.template_hash(),
        schema_hash=template.schema_hash(),
        version=template.version,
        status=template.status,
        schema=template.load_schema(),
    )


@app.post("/v1/presign", response_model=PresignResponse)
def presign_download(payload: PresignRequest) -> PresignResponse:
    storage = S3Storage(bucket=payload.bucket)
    url = storage.presign(payload.object_key, ttl_seconds=payload.ttl_seconds)
    if not url:
        raise HTTPException(status_code=500, detail="presign_failed")
    return PresignResponse(url=url)


@app.post("/v1/sign", response_model=SignResponse)
def sign_document(
    payload: SignRequest,
    request: Request,
    registry: ProviderRegistry = Depends(get_sign_registry),
) -> SignResponse:
    start = time.monotonic()
    request_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")

    input_storage = S3Storage(bucket=payload.input.bucket)
    input_bytes = input_storage.get_bytes(payload.input.object_key)
    if input_bytes is None:
        DOCUMENT_SERVICE_SIGN_TOTAL.labels(status="not_found").inc()
        raise HTTPException(status_code=404, detail="input_not_found")

    input_sha256 = hashlib.sha256(input_bytes).hexdigest()
    if payload.input.sha256 and payload.input.sha256 != input_sha256:
        DOCUMENT_SERVICE_SIGN_TOTAL.labels(status="hash_mismatch").inc()
        raise HTTPException(status_code=409, detail="input_hash_mismatch")

    signed_key, signature_key = _build_signed_keys(payload.output.prefix, payload.input.object_key)
    output_storage = S3Storage(bucket=payload.output.bucket)

    cached_signed = output_storage.head_object(signed_key)
    cached_sig = output_storage.head_object(signature_key)
    if cached_signed and cached_sig:
        signed_sha = cached_signed.sha256 or hashlib.sha256(output_storage.get_bytes(signed_key) or b"").hexdigest()
        sig_sha = cached_sig.sha256 or hashlib.sha256(output_storage.get_bytes(signature_key) or b"").hexdigest()
        DOCUMENT_SERVICE_SIGN_TOTAL.labels(status="cached").inc()
        DOCUMENT_SERVICE_SIGN_DURATION_SECONDS.observe(time.monotonic() - start)
        return SignResponse(
            status="SIGNED",
            provider_request_id=None,
            signed={
                "bucket": cached_signed.bucket,
                "object_key": cached_signed.object_key,
                "sha256": signed_sha,
                "size_bytes": cached_signed.size_bytes,
            },
            signature={
                "bucket": cached_sig.bucket,
                "object_key": cached_sig.object_key,
                "sha256": sig_sha,
                "size_bytes": cached_sig.size_bytes,
            },
            certificate=None,
        )

    try:
        provider = registry.get(payload.provider)
        result = provider.sign(input_bytes, payload.meta)
        signed_sha256 = hashlib.sha256(result.signed_bytes).hexdigest()
        signature_sha256 = hashlib.sha256(result.signature_bytes).hexdigest()
        output_storage.ensure_bucket()
        output_storage.put_bytes(
            signed_key,
            result.signed_bytes,
            content_type="application/pdf",
            metadata={"sha256": signed_sha256},
        )
        output_storage.put_bytes(
            signature_key,
            result.signature_bytes,
            content_type="application/pkcs7-signature",
            metadata={"sha256": signature_sha256},
        )
    except KeyError as exc:
        DOCUMENT_SERVICE_SIGN_TOTAL.labels(status="invalid_provider").inc()
        raise HTTPException(status_code=422, detail="unknown_provider") from exc
    except Exception as exc:  # noqa: BLE001
        DOCUMENT_SERVICE_SIGN_TOTAL.labels(status="fail").inc()
        DOCUMENT_SERVICE_SIGN_ERRORS_TOTAL.labels(code=exc.__class__.__name__).inc()
        logger.exception(
            "document_service.sign_failed",
            extra={"request_id": request_id, "doc_id": payload.document_id, "error": str(exc)},
        )
        raise HTTPException(status_code=502, detail="sign_failed") from exc

    DOCUMENT_SERVICE_SIGN_TOTAL.labels(status="success").inc()
    DOCUMENT_SERVICE_SIGN_DURATION_SECONDS.observe(time.monotonic() - start)
    logger.info(
        "document_service.signed",
        extra={
            "request_id": request_id,
            "doc_id": payload.document_id,
            "provider": payload.provider,
            "signed_key": signed_key,
        },
    )

    return SignResponse(
        status="SIGNED",
        provider_request_id=result.provider_request_id,
        signed={
            "bucket": output_storage.bucket,
            "object_key": signed_key,
            "sha256": signed_sha256,
            "size_bytes": len(result.signed_bytes),
        },
        signature={
            "bucket": output_storage.bucket,
            "object_key": signature_key,
            "sha256": signature_sha256,
            "size_bytes": len(result.signature_bytes),
        },
        certificate=(
            {
                "subject": result.certificate.subject,
                "valid_to": result.certificate.valid_to,
            }
            if result.certificate
            else None
        ),
    )


@app.post("/v1/verify", response_model=VerifyResponse)
def verify_document(
    payload: VerifyRequest,
    request: Request,
    registry: ProviderRegistry = Depends(get_sign_registry),
) -> VerifyResponse:
    request_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")

    input_storage = S3Storage(bucket=payload.input.bucket)
    input_bytes = input_storage.get_bytes(payload.input.object_key)
    if input_bytes is None:
        DOCUMENT_SERVICE_VERIFY_TOTAL.labels(status="not_found").inc()
        raise HTTPException(status_code=404, detail="input_not_found")

    signature_storage = S3Storage(bucket=payload.signature.bucket)
    signature_bytes = signature_storage.get_bytes(payload.signature.object_key)
    if signature_bytes is None:
        DOCUMENT_SERVICE_VERIFY_TOTAL.labels(status="not_found").inc()
        raise HTTPException(status_code=404, detail="signature_not_found")

    try:
        provider = registry.get(payload.provider)
        result = provider.verify(input_bytes, signature_bytes, payload.meta)
    except KeyError as exc:
        DOCUMENT_SERVICE_VERIFY_TOTAL.labels(status="invalid_provider").inc()
        raise HTTPException(status_code=422, detail="unknown_provider") from exc
    except Exception as exc:  # noqa: BLE001
        DOCUMENT_SERVICE_VERIFY_TOTAL.labels(status="fail").inc()
        logger.exception(
            "document_service.verify_failed",
            extra={"request_id": request_id, "error": str(exc)},
        )
        raise HTTPException(status_code=502, detail="verify_failed") from exc

    DOCUMENT_SERVICE_VERIFY_TOTAL.labels(status="success" if result.verified else "rejected").inc()
    return VerifyResponse(
        status="VERIFIED" if result.verified else "REJECTED",
        verified=result.verified,
        error_code=result.error_code,
        certificate=(
            {
                "subject": result.certificate.subject,
                "valid_to": result.certificate.valid_to,
            }
            if result.certificate
            else None
        ),
    )


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


def _build_signed_keys(prefix: str, input_key: str) -> tuple[str, str]:
    trimmed_prefix = prefix.rstrip("/")
    filename = input_key.rsplit("/", 1)[-1]
    base = filename.rsplit(".", 1)[0]
    signed_key = f"{trimmed_prefix}/{base}.signed.pdf"
    signature_key = f"{trimmed_prefix}/{base}.sig.p7s"
    return signed_key, signature_key
