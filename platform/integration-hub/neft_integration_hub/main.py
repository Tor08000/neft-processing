from __future__ import annotations

import logging
import os
import re
import socket
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Any, Callable
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
except ModuleNotFoundError:  # pragma: no cover - test/runtime packaging fallback
    CONTENT_TYPE_LATEST = "text/plain"

    class _MetricStub:
        def labels(self, *args, **kwargs):
            return self

        def inc(self, *args, **kwargs):
            return None

        def set(self, *args, **kwargs):
            return None

        def observe(self, *args, **kwargs):
            return None

    def Counter(*args, **kwargs):  # type: ignore[misc]
        return _MetricStub()

    def Gauge(*args, **kwargs):  # type: ignore[misc]
        return _MetricStub()

    def generate_latest():
        return b""

from neft_integration_hub.celery_app import celery_app
from neft_integration_hub.db import get_db, get_schema_health, init_db
from neft_integration_hub.metrics import (
    WEBHOOK_ALERTS_ACTIVE_TOTAL,
    WEBHOOK_DELIVERY_SUCCESS_RATIO,
    WEBHOOK_PAUSED_ENDPOINTS_TOTAL,
    WEBHOOK_REPLAY_SCHEDULED_TOTAL,
)
from neft_integration_hub.models import (
    EdoDocument,
    EdoStubDocument,
    EdoStubStatus,
    WebhookAlert,
    WebhookAlertType,
    WebhookDelivery,
    WebhookEndpoint,
    WebhookSubscription,
)
from neft_integration_hub.schemas import (
    OtpSendRequest,
    OtpSendResponse,
    DispatchRequest,
    DispatchResponse,
    NotificationSendRequest,
    NotificationSendResponse,
    NotifyEmailSendRequest,
    NotifyEmailSendResponse,
    EdoDocumentResponse,
    EdoIntSendRequest,
    EdoIntSendResponse,
    EdoIntStatusResponse,
    EdoStubSendRequest,
    EdoStubSendResponse,
    EdoStubSimulateRequest,
    EdoStubStatusResponse,
    WebhookAlertResponse,
    WebhookDeliveryAttemptResponse,
    WebhookDeliveryDetailResponse,
    WebhookDeliveryResponse,
    WebhookDeliveryRetryResponse,
    WebhookEndpointCreate,
    WebhookEndpointResponse,
    WebhookEndpointSecretResponse,
    WebhookEndpointUpdateRequest,
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
    WebhookSubscriptionUpdateRequest,
    WebhookTestDeliveryRequest,
    WebhookTestEndpointRequest,
    WebhookTestResponse,
)
from neft_integration_hub.services.edo_service import dispatch_request, poll_document, send_document
from neft_integration_hub.services.edo_stub import create_stub_document, get_stub_document, simulate_status
from neft_integration_hub.services.webhook_intake import record_intake_event, verify_signature
from neft_integration_hub.services.webhooks import (
    build_event_envelope,
    compute_sla,
    create_endpoint,
    create_subscription,
    delete_subscription,
    evaluate_alerts,
    enqueue_delivery,
    list_deliveries,
    list_endpoints,
    list_subscriptions,
    pause_endpoint,
    resume_endpoint,
    retry_delivery,
    rotate_secret,
    schedule_replay,
    update_endpoint,
    update_subscription,
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

_PLACEHOLDER_SECRETS = {"change-me", "changeme", "dev-key", "dev-secret", "test", "dummy", "placeholder"}
_PLACEHOLDER_URLS = {"https://diadok.example.com", "http://diadok.example.com"}


def _email_provider_enabled() -> bool:
    if settings.email_provider_mode in {"mock", "sandbox"}:
        return True
    if settings.email_provider_mode == "smtp":
        return bool(settings.smtp_host)
    return False


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
) -> dict[str, Any]:
    return {
        "service": SERVICE_NAME,
        "provider": provider,
        "mode": mode,
        "status": status,
        "configured": configured,
        "last_success_at": None,
        "last_error_code": last_error_code,
        "message": message,
        "sandbox_proof": status == "CONFIGURED" and mode == "sandbox",
        "last_attempt": None,
        "retryable": False,
    }


def _mode_status(mode: str, *, configured: bool, unsupported: bool = False) -> str:
    if unsupported:
        return "UNSUPPORTED"
    if mode in {"", "disabled"}:
        return "DISABLED"
    if mode == "degraded":
        return "DEGRADED"
    if mode in {"mock", "stub", "sandbox"}:
        return "CONFIGURED"
    return "HEALTHY" if configured else "DEGRADED"


def _sandbox_or_mode_health(provider: str, raw_mode: str, message: str, missing_code: str) -> dict[str, Any]:
    mode = _provider_mode(raw_mode, "sandbox")
    sandbox_configured = mode == "sandbox"
    return _provider_health(
        provider=provider,
        mode=mode,
        status="CONFIGURED" if sandbox_configured else _mode_status(mode, configured=False),
        configured=sandbox_configured,
        last_error_code=None if sandbox_configured else missing_code,
        message=message,
    )


def _real_secret(value: str | None) -> bool:
    normalized = (value or "").strip()
    return bool(normalized) and normalized.lower() not in _PLACEHOLDER_SECRETS


def _real_provider_url(value: str | None) -> bool:
    normalized = (value or "").strip().rstrip("/")
    return bool(normalized) and normalized.lower() not in _PLACEHOLDER_URLS


def _external_provider_health() -> list[dict[str, Any]]:
    diadok_mode = _provider_mode(settings.diadok_mode, "sandbox")
    sbis_mode = _provider_mode(settings.sbis_mode, "sandbox")
    diadok_configured = diadok_mode == "sandbox" or (
        _real_provider_url(settings.diadok_base_url) and _real_secret(settings.diadok_api_token)
    )
    diadok_status = _mode_status(
        diadok_mode,
        configured=diadok_configured,
        unsupported=diadok_mode not in {"mock", "stub", "sandbox", "production", "disabled", "degraded"},
    )

    email_mode = _provider_mode(settings.email_provider_mode, "sandbox")
    email_configured = email_mode == "smtp" and bool((settings.smtp_host or "").strip())
    email_status = _mode_status(
        email_mode,
        configured=email_configured or email_mode == "sandbox",
        unsupported=email_mode not in {"mock", "smtp", "sandbox", "disabled", "degraded"},
    )

    otp_mode = _provider_mode(settings.otp_provider_mode, "sandbox")
    otp_provider = (settings.otp_sms_provider or "").strip()
    otp_status = _mode_status(
        otp_mode,
        configured=bool(otp_provider) or otp_mode == "sandbox",
        unsupported=otp_mode == "production" and not otp_provider,
    )
    if otp_mode == "sandbox":
        otp_status = "CONFIGURED"
    elif otp_mode == "production" and otp_provider:
        otp_status = "DEGRADED"

    notifications_mode = _provider_mode(settings.notifications_mode, "sandbox")
    notifications_status = _mode_status(
        notifications_mode,
        configured=bool((settings.notifications_email_provider or "").strip()) or email_configured or notifications_mode == "sandbox",
        unsupported=notifications_mode not in {"mock", "disabled", "degraded", "sandbox", "production"},
    )
    if notifications_mode == "sandbox":
        notifications_status = "CONFIGURED"
    elif notifications_mode == "production":
        notifications_status = "DEGRADED"

    webhook_secret_configured = _real_secret(settings.webhook_intake_secret)
    webhook_status = "HEALTHY" if webhook_secret_configured and not settings.webhook_allow_unsigned else "DEGRADED"
    return [
        _provider_health(
            provider="diadok",
            mode=diadok_mode,
            status=diadok_status,
            configured=diadok_configured or diadok_mode in {"mock", "stub", "sandbox"},
            last_error_code=None if diadok_status in {"HEALTHY", "CONFIGURED"} else "diadok_not_configured",
            message="DIADOK EDO transport" if diadok_status in {"HEALTHY", "CONFIGURED"} else "DIADOK requires base URL and API token before provider smoke can pass",
        ),
        _provider_health(
            provider="sbis",
            mode=sbis_mode,
            status="CONFIGURED" if sbis_mode == "sandbox" else _mode_status(sbis_mode, configured=False, unsupported=sbis_mode == "unsupported"),
            configured=sbis_mode == "sandbox",
            last_error_code=None if sbis_mode == "sandbox" else "sbis_not_configured",
            message="SBIS EDO sandbox transport" if sbis_mode == "sandbox" else "SBIS EDO transport is not configured",
        ),
        _provider_health(
            provider="smtp_email",
            mode=email_mode,
            status=email_status,
            configured=email_configured or email_mode in {"mock", "sandbox"},
            last_error_code=None if email_status in {"HEALTHY", "CONFIGURED", "DISABLED"} else "smtp_not_configured",
            message="SMTP email provider" if email_status in {"HEALTHY", "CONFIGURED"} else "Email provider is disabled or missing SMTP_HOST",
        ),
        _provider_health(
            provider="otp_sms",
            mode=otp_mode,
            status=otp_status,
            configured=bool(otp_provider) or otp_mode == "sandbox",
            last_error_code=(
                "otp_vendor_not_selected"
                if otp_status == "UNSUPPORTED"
                else "otp_transport_not_implemented"
                if otp_status == "DEGRADED"
                else None
            ),
            message="OTP/SMS vendor adapter is provider-gated until concrete vendor credentials are supplied",
        ),
        _provider_health(
            provider="notifications",
            mode=notifications_mode,
            status=notifications_status,
            configured=notifications_status in {"HEALTHY", "CONFIGURED"},
            last_error_code=None if notifications_status in {"HEALTHY", "CONFIGURED", "DISABLED"} else "notification_transport_not_configured",
            message="Webhook delivery remains runtime-backed; email/multichannel delivery is provider-gated",
        ),
        _provider_health(
            provider="webhook_intake",
            mode="production" if not settings.webhook_allow_unsigned else "dev_unsigned_allowed",
            status=webhook_status,
            configured=webhook_secret_configured,
            last_error_code=None if webhook_status == "HEALTHY" else "webhook_signature_policy_degraded",
            message="Signed webhook intake policy" if webhook_status == "HEALTHY" else "Unsigned webhook intake is allowed only outside production",
        ),
        _sandbox_or_mode_health(
            "bank_api",
            settings.bank_api_mode,
            "Bank API sandbox contract proof is enabled without production credentials",
            "bank_api_not_configured",
        ),
        _sandbox_or_mode_health(
            "erp_1c",
            settings.erp_1c_mode,
            "ERP/1C sandbox contract proof is enabled without production credentials",
            "erp_1c_not_configured",
        ),
        _sandbox_or_mode_health(
            "fuel_provider",
            settings.fuel_provider_mode,
            "Fuel provider sandbox contract proof is enabled without production credentials",
            "fuel_provider_not_configured",
        ),
        _sandbox_or_mode_health(
            "logistics_provider",
            settings.logistics_provider_mode,
            "Logistics provider sandbox contract proof is enabled without production credentials",
            "logistics_provider_not_configured",
        ),
    ]


def _verify_intake_signature(raw_body: bytes, signature_header: str) -> tuple[bool, str | None]:
    for secret in (settings.webhook_intake_secret, settings.webhook_intake_next_secret):
        if not secret:
            continue
        verified, normalized = verify_signature(raw_body, signature_header, secret)
        if verified:
            return True, normalized
    return False, None




def _prod_mode() -> bool:
    return (settings.app_env or "").strip().lower() in {"prod", "production"}


def _mock_overrides_allowed() -> bool:
    return (os.getenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "0").strip() == "1")


def _enforce_prod_guardrails() -> None:
    if not _prod_mode() or _mock_overrides_allowed():
        return
    guarded = {
        "DIADOK_MODE": settings.diadok_mode,
        "NOTIFICATIONS_MODE": settings.notifications_mode,
        "EMAIL_PROVIDER_MODE": settings.email_provider_mode,
        "OTP_PROVIDER_MODE": settings.otp_provider_mode,
    }
    risky = {k: v for k, v in guarded.items() if (v or "").strip().lower() in {"mock", "stub"}}
    if risky:
        raise RuntimeError(
            "prod guardrail violation: mock/stub providers are forbidden in prod. "
            "Set ALLOW_MOCK_PROVIDERS_IN_PROD=1 only for explicit emergency override. "
            f"Violations: {risky}"
        )
    if settings.webhook_allow_unsigned:
        raise RuntimeError(
            "prod guardrail violation: unsigned webhook intake is forbidden in prod. "
            "Set WEBHOOK_ALLOW_UNSIGNED=false or use ALLOW_MOCK_PROVIDERS_IN_PROD=1 only for explicit emergency override."
        )
def _ensure_email_provider_or_503() -> None:
    if not getattr(app.state, "email_provider_enabled", True):
        raise HTTPException(
            status_code=503,
            detail=_error_detail(
                category="degraded",
                error="email_provider_not_configured",
                message="Email provider is disabled or not configured for this environment",
                provider=settings.email_provider_mode or "disabled",
            ),
        )


def _error_detail(
    *,
    category: str,
    error: str,
    message: str,
    provider: str | None = None,
    mode: str | None = None,
    retryable: bool | None = None,
) -> dict:
    payload = {
        "category": category,
        "error": error,
        "message": message,
    }
    if provider:
        payload["provider"] = provider
    if mode:
        payload["mode"] = mode
    if retryable is not None:
        payload["retryable"] = retryable
    return payload


def _raise_integration_http_error(
    status_code: int,
    *,
    category: str,
    error: str,
    message: str,
    provider: str | None = None,
    mode: str | None = None,
    retryable: bool | None = None,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=_error_detail(
            category=category,
            error=error,
            message=message,
            provider=provider,
            mode=mode,
            retryable=retryable,
        ),
    )


@app.on_event("startup")
def startup() -> None:
    _enforce_prod_guardrails()
    init_db()
    if settings.notifications_mode == "real":
        logger.warning("notifications_real_mode_has_no_transport_adapter")

    app.state.email_provider_enabled = _email_provider_enabled()
    if not app.state.email_provider_enabled:
        logger.error(
            "email provider disabled: app_env=%s email_provider_mode=%s",
            settings.app_env,
            settings.email_provider_mode,
        )

    logger.info(
        "running in %s mode",
        settings.app_env.upper(),
        extra={
            "app_env": settings.app_env,
            "use_stub_edo": settings.use_stub_edo,
            "notifications_mode": settings.notifications_mode,
            "otp_provider_mode": settings.otp_provider_mode,
            "email_provider_mode": settings.email_provider_mode,
            "webhook_allow_unsigned": settings.webhook_allow_unsigned,
        },
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
def health(response: Response) -> dict:
    email_provider_enabled = bool(getattr(app.state, "email_provider_enabled", True))
    schema_health = get_schema_health()
    if not schema_health["ready"]:
        response.status_code = 503
    external_providers = _external_provider_health()
    return {
        "status": "ok" if schema_health["ready"] else "degraded",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "email_provider": "enabled" if email_provider_enabled else "disabled",
        "provider_modes": {
            "diadok": settings.diadok_mode,
            "sbis": settings.sbis_mode,
            "otp": settings.otp_provider_mode,
            "notifications": settings.notifications_mode,
            "email": settings.email_provider_mode,
        },
        "webhook_signature_required": not settings.webhook_allow_unsigned,
        "external_providers": external_providers,
        "providers": external_providers,
        "database": schema_health,
    }


@app.get("/api/int/v1/providers/health")
def providers_health(x_internal_token: str | None = Header(default=None, alias="X-Internal-Token")) -> dict:
    if settings.internal_token and x_internal_token != settings.internal_token:
        raise HTTPException(status_code=401, detail="invalid_internal_token")
    providers = _external_provider_health()
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "providers": providers,
        "external_providers": providers,
    }


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
        verified, _normalized = _verify_intake_signature(raw_body, signature_header)
        if not verified:
            raise HTTPException(status_code=401, detail="invalid_signature")
    elif not settings.webhook_allow_unsigned:
        raise HTTPException(status_code=401, detail="signature_required")

    intake = record_intake_event(
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
    return WebhookIntakeResponse(
        event_id=intake.record.event_id or payload.event_id,
        status="duplicate" if intake.duplicate else "accepted",
        verified=verified,
        duplicate=intake.duplicate,
    )






_OTP_IDEMPOTENCY: dict[str, tuple[float, dict]] = {}


def _cleanup_otp_idempotency(ttl_seconds: int = 1800) -> None:
    now = time.time()
    for key, (ts, _) in list(_OTP_IDEMPOTENCY.items()):
        if now - ts > ttl_seconds:
            _OTP_IDEMPOTENCY.pop(key, None)


def _validate_otp_destination(channel: str, destination: str) -> bool:
    if channel == "sms":
        return bool(re.match(r"^\+?[0-9]{10,15}$", destination))
    if channel == "telegram":
        return bool(destination.strip())
    return False


@app.post("/api/int/v1/otp/send", response_model=OtpSendResponse)
def send_otp(payload: OtpSendRequest, x_internal_token: str | None = Header(default=None, alias="X-Internal-Token")) -> OtpSendResponse:
    if settings.internal_token and x_internal_token != settings.internal_token:
        raise HTTPException(status_code=401, detail="invalid_internal_token")
    _cleanup_otp_idempotency()
    channel = payload.channel.lower()
    if not _validate_otp_destination(channel, payload.destination):
        raise HTTPException(status_code=422, detail={"error_code": "invalid_destination", "message": "Invalid OTP destination"})

    cached = _OTP_IDEMPOTENCY.get(payload.idempotency_key)
    if cached is not None:
        return OtpSendResponse(**cached[1])

    if settings.otp_provider_mode in {"mock", "sandbox"}:
        mode = settings.otp_provider_mode
        result = {"provider_message_id": f"{mode}:{uuid4()}", "status": "sent", "mode": mode}
        _OTP_IDEMPOTENCY[payload.idempotency_key] = (time.time(), result)
        return OtpSendResponse(**result)

    if settings.otp_provider_mode in {"", "disabled", "degraded"}:
        _raise_integration_http_error(
            503,
            category="degraded",
            error="otp_provider_degraded",
            message="OTP transport is not configured in integration-hub",
            provider=channel,
            mode=settings.otp_provider_mode or "degraded",
            retryable=False,
        )

    if channel == "sms" and not settings.otp_sms_provider:
        _raise_integration_http_error(
            503,
            category="degraded",
            error="otp_provider_not_configured",
            message="SMS provider is not configured",
            provider="sms",
            mode=settings.otp_provider_mode,
            retryable=False,
        )
    if channel == "telegram" and settings.otp_telegram_provider == "bot" and not settings.otp_tg_bot_token:
        _raise_integration_http_error(
            503,
            category="degraded",
            error="otp_provider_not_configured",
            message="Telegram provider is not configured",
            provider="telegram",
            mode=settings.otp_provider_mode,
            retryable=False,
        )

    _raise_integration_http_error(
        503,
        category="degraded",
        error="otp_transport_not_implemented",
        message="OTP provider mode is configured but no real transport adapter is wired in integration-hub",
        provider=channel,
        mode=settings.otp_provider_mode,
        retryable=False,
    )

@app.post("/api/int/v1/notifications/send", response_model=NotificationSendResponse)
def send_notification(payload: NotificationSendRequest, request: Request) -> NotificationSendResponse:
    request_id = getattr(request.state, "request_id", None)
    if settings.notifications_mode in {"mock", "sandbox"}:
        logger.info(
            "notifications.sandbox" if settings.notifications_mode == "sandbox" else "notifications.mock",
            extra={"request_id": request_id, "payload": payload.model_dump()},
        )
        return NotificationSendResponse(
            status="accepted",
            mode=settings.notifications_mode,
            provider=settings.notifications_mode,
            provider_message_id=f"{settings.notifications_mode}:{uuid4()}",
        )

    if settings.notifications_mode in {"", "disabled", "degraded"}:
        _raise_integration_http_error(
            503,
            category="degraded",
            error="notifications_degraded",
            message="Notifications transport is not configured in integration-hub",
            provider=payload.channel.lower(),
            mode=settings.notifications_mode or "degraded",
            retryable=False,
        )

    _raise_integration_http_error(
        503,
        category="degraded",
        error="notifications_transport_not_implemented",
        message="Integration-hub does not own notification template rendering/transport for this provider yet",
        provider=(settings.notifications_email_provider or payload.channel).lower(),
        mode=settings.notifications_mode,
        retryable=False,
    )


def _validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def _send_smtp_email(payload: NotifyEmailSendRequest) -> str:
    if not settings.smtp_host:
        raise RuntimeError("smtp_host_missing")
    message = EmailMessage()
    message_id = make_msgid(domain="neft.local")
    message["Message-ID"] = message_id
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message["To"] = payload.to
    message["Subject"] = payload.subject
    message.set_content(payload.text or "")
    if payload.html:
        message.add_alternative(payload.html, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_tls:
            smtp.starttls()
        if settings.smtp_user and settings.smtp_password:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
    return f"smtp:{message_id}"


def _deliver_email(payload: NotifyEmailSendRequest) -> NotifyEmailSendResponse:
    _ensure_email_provider_or_503()

    if not _validate_email(payload.to):
        raise HTTPException(status_code=400, detail="invalid_email")

    if settings.email_provider_mode in {"mock", "sandbox"}:
        mode = settings.email_provider_mode
        logger.info("notify.email.%s", mode, extra={"to": payload.to, "subject": payload.subject, "meta": payload.meta})
        return NotifyEmailSendResponse(status="sent", message_id=f"{mode}:{uuid4()}", mode=mode)

    if settings.email_provider_mode != "smtp":
        _raise_integration_http_error(
            503,
            category="degraded",
            error="email_provider_not_configured",
            message="Email provider mode is disabled or not supported",
            provider=settings.email_provider_mode,
            mode=settings.email_provider_mode,
            retryable=False,
        )

    try:
        message_id = _send_smtp_email(payload)
    except socket.timeout:
        _raise_integration_http_error(
            504,
            category="timeout",
            error="email_provider_timeout",
            message="Email provider timed out",
            provider="smtp",
            mode=settings.email_provider_mode,
            retryable=True,
        )
    except TimeoutError:
        _raise_integration_http_error(
            504,
            category="timeout",
            error="email_provider_timeout",
            message="Email provider timed out",
            provider="smtp",
            mode=settings.email_provider_mode,
            retryable=True,
        )
    except smtplib.SMTPAuthenticationError:
        _raise_integration_http_error(
            502,
            category="auth_error",
            error="email_provider_auth_error",
            message="SMTP authentication failed",
            provider="smtp",
            mode=settings.email_provider_mode,
            retryable=False,
        )
    except RuntimeError as exc:
        _raise_integration_http_error(
            503,
            category="provider_error",
            error="email_provider_unavailable",
            message=str(exc),
            provider="smtp",
            mode=settings.email_provider_mode,
            retryable=True,
        )
    except Exception as exc:  # noqa: BLE001
        _raise_integration_http_error(
            503,
            category="provider_error",
            error="email_provider_unavailable",
            message=str(exc),
            provider="smtp",
            mode=settings.email_provider_mode,
            retryable=True,
        )

    return NotifyEmailSendResponse(status="sent", message_id=message_id, mode="smtp")


@app.post("/api/int/notify/email/send", response_model=NotifyEmailSendResponse)
def send_email(payload: NotifyEmailSendRequest) -> NotifyEmailSendResponse:
    return _deliver_email(payload)




def _edo_provider_mode_label(provider: str | None = None) -> str:
    provider_name = (provider or "DIADOK").strip().upper()
    raw_mode = settings.sbis_mode if provider_name == "SBIS" else settings.diadok_mode
    mode = (raw_mode or "").strip().lower()
    if mode in {"mock", "stub", "sandbox", "disabled", "degraded"}:
        return mode
    return "production"


def _edo_provider_name(provider: str) -> str:
    normalized = (provider or "").strip().upper()
    if not normalized or normalized == "MOCK":
        raise HTTPException(status_code=422, detail="edo_provider_not_configured")
    if normalized not in {"DIADOK", "SBIS"}:
        _raise_integration_http_error(
            422,
            category="degraded",
            error="edo_provider_not_supported",
            message=f"EDO provider {normalized.lower()} is not wired in integration-hub",
            provider=normalized.lower(),
            mode=_edo_provider_mode_label(normalized),
            retryable=False,
        )
    return normalized


def _edo_int_status(status: str) -> str:
    normalized = (status or "").strip().upper()
    if normalized == "UPLOADING":
        return "SENDING"
    if normalized in {"SIGNED_BY_COUNTERPARTY", "SIGNED_BY_US"}:
        return "SIGNED"
    if normalized == "FAILED":
        return "ERROR"
    return normalized or "ERROR"


def _edo_int_dispatch_request(payload: EdoIntSendRequest) -> DispatchRequest:
    if not payload.document.files:
        raise HTTPException(status_code=422, detail="edo_document_files_missing")
    artifact = payload.document.files[0]
    object_key = artifact.storage_key
    if not object_key:
        raise HTTPException(status_code=422, detail="edo_document_artifact_missing")
    meta = payload.document.meta or {}
    return DispatchRequest(
        document_id=payload.document.document_id,
        signature_id=None,
        provider=_edo_provider_name(payload.provider),
        artifact={
            "bucket": settings.s3_bucket_docs,
            "object_key": object_key,
            "sha256": artifact.sha256,
        },
        counterparty={
            "inn": str(meta.get("counterparty_inn") or ""),
            "kpp": str(meta.get("counterparty_kpp") or ""),
            "edo_id": meta.get("counterparty_edo_id"),
        },
        idempotency_key=payload.idempotency_key,
        meta={
            "client_id": payload.document.client_id,
            "title": payload.document.title,
            "category": payload.document.category,
            "provider_request": payload.provider,
            "files": [item.model_dump() for item in payload.document.files],
            **meta,
        },
    )


def _edo_int_send_response(record: EdoDocument) -> EdoIntSendResponse:
    meta = record.meta or {}
    return EdoIntSendResponse(
        edo_message_id=record.id,
        edo_status=_edo_int_status(record.status),
        provider=str(record.provider or "").lower(),
        provider_mode=_edo_provider_mode_label(record.provider),
        last_error=record.last_error,
        last_error_type=meta.get("last_error_type"),
        retrying=record.status == "QUEUED" and bool(record.last_error),
    )


def _edo_int_status_response(record: EdoDocument, provider: str | None = None) -> EdoIntStatusResponse:
    meta = record.meta or {}
    return EdoIntStatusResponse(
        edo_message_id=record.id,
        edo_status=_edo_int_status(record.status),
        provider_status_raw={
            "provider": (provider or record.provider or "").lower(),
            "provider_message_id": record.provider_message_id,
            "provider_document_id": record.provider_document_id,
            "status": record.status,
            "last_error": record.last_error,
            "last_error_code": meta.get("last_error_code"),
            "last_error_type": meta.get("last_error_type"),
            "retryable": meta.get("last_error_retryable"),
            "provider_mode": _edo_provider_mode_label(provider or record.provider),
        },
        updated_at=record.last_status_at or record.updated_at or record.created_at,
    )


@app.post("/api/int/v1/edo/send", response_model=EdoIntSendResponse)
def edo_int_send(payload: EdoIntSendRequest, db: Session = Depends(get_db)) -> EdoIntSendResponse:
    try:
        record = dispatch_request(db, _edo_int_dispatch_request(payload))
    except ValueError as exc:
        if str(exc) == "idempotency_conflict":
            _raise_integration_http_error(
                409,
                category="provider_error",
                error="idempotency_conflict",
                message="EDO dispatch already exists for this document/provider with another idempotency key",
                provider=payload.provider.lower(),
                mode=_edo_provider_mode_label(payload.provider),
                retryable=False,
            )
        raise
    record = send_document(db, record.id)
    if record.status == "FAILED":
        meta = record.meta or {}
        status_code = 504 if meta.get("last_error_type") == "timeout" else 503
        _raise_integration_http_error(
            status_code,
            category=meta.get("last_error_type") or "provider_error",
            error=meta.get("last_error_code") or "edo_provider_unavailable",
            message=record.last_error or "EDO provider is unavailable",
            provider=str(record.provider or "").lower(),
            mode=_edo_provider_mode_label(record.provider),
            retryable=bool(meta.get("last_error_retryable")),
        )
    return _edo_int_send_response(record)


@app.get("/api/int/v1/edo/{edo_message_id}/status", response_model=EdoIntStatusResponse)
def edo_int_status(edo_message_id: str, provider: str | None = None, db: Session = Depends(get_db)) -> EdoIntStatusResponse:
    record = db.query(EdoDocument).filter(EdoDocument.id == edo_message_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="edo_document_not_found")
    record = poll_document(db, edo_message_id)
    return _edo_int_status_response(record, provider=provider)

@app.post("/v1/edo/dispatch", response_model=DispatchResponse)
def edo_dispatch(payload: DispatchRequest, db: Session = Depends(get_db)) -> DispatchResponse:
    _edo_provider_name(payload.provider)
    try:
        record = dispatch_request(db, payload)
    except ValueError as exc:
        if str(exc) == "idempotency_conflict":
            _raise_integration_http_error(
                409,
                category="provider_error",
                error="idempotency_conflict",
                message="EDO dispatch already exists for this document/provider with another idempotency key",
                provider=payload.provider.lower(),
                mode=_edo_provider_mode_label(payload.provider),
                retryable=False,
            )
        raise
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
        last_error_type=(record.meta or {}).get("last_error_type"),
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




def _webhook_endpoint_response(endpoint: WebhookEndpoint) -> WebhookEndpointResponse:
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


def _webhook_subscription_response(subscription: WebhookSubscription) -> WebhookSubscriptionResponse:
    return WebhookSubscriptionResponse(
        id=subscription.id,
        endpoint_id=subscription.endpoint_id,
        event_type=subscription.event_type,
        schema_version=subscription.schema_version,
        filters=subscription.filters,
        enabled=subscription.enabled,
    )


def _webhook_delivery_detail_response(
    delivery: WebhookDelivery,
    endpoint: WebhookEndpoint | None,
) -> WebhookDeliveryDetailResponse:
    envelope = delivery.payload if isinstance(delivery.payload, dict) else None
    correlation_id = envelope.get("correlation_id") if isinstance(envelope, dict) else None
    if not isinstance(correlation_id, str):
        correlation_id = None
    attempts = []
    if delivery.attempt > 0:
        attempts.append(
            WebhookDeliveryAttemptResponse(
                attempt=delivery.attempt,
                http_status=delivery.last_http_status,
                error=delivery.last_error,
                latency_ms=delivery.latency_ms,
                delivered_at=delivery.delivered_at,
                next_retry_at=delivery.next_retry_at,
                correlation_id=correlation_id,
            )
        )
    return WebhookDeliveryDetailResponse(
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
        endpoint_url=endpoint.url if endpoint else None,
        envelope=envelope,
        headers={
            "Content-Type": "application/json",
            "X-NEFT-Event-Id": delivery.event_id,
        },
        attempts=attempts,
        error=delivery.last_error,
        correlation_id=correlation_id,
    )


def _webhook_test_response(event_id: str, delivery: WebhookDelivery) -> WebhookTestResponse:
    return WebhookTestResponse(
        event_id=event_id,
        delivery_id=delivery.id,
        status=delivery.status,
        http_status=delivery.last_http_status,
        latency_ms=delivery.latency_ms,
        error=delivery.last_error,
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
    return [_webhook_endpoint_response(endpoint) for endpoint in endpoints]


@app.patch("/v1/webhooks/endpoints/{endpoint_id}", response_model=WebhookEndpointResponse)
def update_webhook_endpoint_route(
    endpoint_id: str,
    payload: WebhookEndpointUpdateRequest,
    db: Session = Depends(get_db),
) -> WebhookEndpointResponse:
    endpoint = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="endpoint_not_found")
    if payload.status is None and payload.url is None:
        raise HTTPException(status_code=400, detail="empty_patch")
    endpoint = update_endpoint(db, endpoint, status=payload.status, url=payload.url)
    return _webhook_endpoint_response(endpoint)


@app.post("/v1/webhooks/endpoints/{endpoint_id}/test", response_model=WebhookTestResponse)
def test_webhook_endpoint(
    endpoint_id: str,
    payload: WebhookTestEndpointRequest | None = None,
    db: Session = Depends(get_db),
) -> WebhookTestResponse:
    endpoint = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="endpoint_not_found")
    event_id = str(uuid4())
    envelope = build_event_envelope(
        event_id=event_id,
        event_type=payload.event_type if payload and payload.event_type else "webhook.test",
        correlation_id=event_id,
        owner=WebhookOwner(type=endpoint.owner_type, id=endpoint.owner_id),
        payload=payload.payload if payload and payload.payload is not None else {"message": "test"},
    )
    delivery = enqueue_delivery(db, endpoint=endpoint, envelope=envelope)
    celery_app.send_task("webhook.deliver", args=[delivery.id])
    return _webhook_test_response(event_id, delivery)


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
    return _webhook_test_response(event_id, delivery)


@app.get("/v1/webhooks/subscriptions", response_model=list[WebhookSubscriptionResponse])
def get_webhook_subscriptions(
    endpoint_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[WebhookSubscriptionResponse]:
    subscriptions = list_subscriptions(db, endpoint_id=endpoint_id)
    return [_webhook_subscription_response(subscription) for subscription in subscriptions]


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
    return _webhook_subscription_response(subscription)


@app.patch("/v1/webhooks/subscriptions/{subscription_id}", response_model=WebhookSubscriptionResponse)
def update_webhook_subscription_route(
    subscription_id: str,
    payload: WebhookSubscriptionUpdateRequest,
    db: Session = Depends(get_db),
) -> WebhookSubscriptionResponse:
    subscription = db.query(WebhookSubscription).filter(WebhookSubscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="subscription_not_found")
    subscription = update_subscription(db, subscription, enabled=payload.enabled)
    return _webhook_subscription_response(subscription)


@app.delete("/v1/webhooks/subscriptions/{subscription_id}", status_code=204)
def delete_webhook_subscription_route(subscription_id: str, db: Session = Depends(get_db)) -> Response:
    subscription = db.query(WebhookSubscription).filter(WebhookSubscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="subscription_not_found")
    delete_subscription(db, subscription)
    return Response(status_code=204)


@app.get("/v1/webhooks/deliveries", response_model=list[WebhookDeliveryResponse])
def get_webhook_deliveries(
    endpoint_id: str | None = None,
    status: str | None = None,
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    limit: int | None = None,
    event_type: str | None = None,
    event_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[WebhookDeliveryResponse]:
    try:
        deliveries = list_deliveries(
            db,
            endpoint_id=endpoint_id,
            status=status,
            from_value=date_from,
            to_value=date_to,
            limit=limit,
            event_type=event_type,
            event_id=event_id,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_delivery_filters")
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


@app.get("/v1/webhooks/deliveries/{delivery_id}", response_model=WebhookDeliveryDetailResponse)
def get_webhook_delivery_detail(delivery_id: str, db: Session = Depends(get_db)) -> WebhookDeliveryDetailResponse:
    delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="delivery_not_found")
    endpoint = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == delivery.endpoint_id).first()
    return _webhook_delivery_detail_response(delivery, endpoint)


@app.post("/v1/webhooks/deliveries/{delivery_id}/retry", response_model=WebhookDeliveryRetryResponse)
def retry_webhook_delivery_route(delivery_id: str, db: Session = Depends(get_db)) -> WebhookDeliveryRetryResponse:
    delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="delivery_not_found")
    try:
        delivery = retry_delivery(db, delivery)
    except ValueError:
        raise HTTPException(status_code=404, detail="endpoint_not_found")
    if delivery.next_retry_at is not None:
        celery_app.send_task("webhook.deliver", args=[delivery.id])
    return WebhookDeliveryRetryResponse(delivery_id=delivery.id)


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
    request_id = str(uuid4())
    idempotency_key = str(payload.get("idempotency_key") or f"fuel:{trip_id}:{distance_km}")
    return {
        "ok": True,
        "request_id": request_id,
        "trip_id": trip_id,
        "liters": liters,
        "method": "integration_hub",
        "provider_mode": _provider_mode(settings.fuel_provider_mode, "sandbox"),
        "sandbox_proof": {
            "contract": "fuel_consumption.v1",
            "formula": "round(distance_km * 0.28, 2)",
            "distance_km": distance_km,
            "vehicle_kind": str(payload.get("vehicle_kind", "truck")),
            "idempotency_key": idempotency_key,
        },
        "last_attempt": {
            "attempt": 1,
            "status": "success",
            "provider": "fuel_provider",
            "mode": _provider_mode(settings.fuel_provider_mode, "sandbox"),
            "request_id": request_id,
        },
        "retryable": False,
        "idempotency_key": idempotency_key,
    }
