from __future__ import annotations

import os
from datetime import datetime, timezone
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import PlainTextResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from neft_shared.logging_setup import get_logger, init_logging

from app.api.routes import router as api_router
from app.db import get_db, get_sessionmaker, init_db
from app.routers.achievements import router as achievements_router
from app.routers.admin import router as admin_router
from app.routers.client import router as client_router
from app.routers.client_fleet import router as fleet_router
from app.routers.client_documents import router as client_documents_router
from app.routers.admin_auth_gateway import router as admin_auth_gateway_router
from app.routers.client_auth_gateway import router as client_auth_gateway_router
from app.routers.client_me import router as client_me_router
from app.routers.document_templates import router as document_templates_router
from app.routers.legal_gate import router as legal_gate_router
from app.routers.client_marketplace import router as client_marketplace_router
from app.routers.client_marketplace_orders import router as client_marketplace_orders_router
from app.routers.client_marketplace_deals import router as client_marketplace_deals_router
from app.routers.client_service_bookings import router as client_service_bookings_router
from app.routers.client_service_completion_proofs import (
    router as client_service_completion_proofs_router,
)
from app.routers.client_portal import router as client_portal_router
from app.routers.client_onboarding import router as client_onboarding_router
from app.routers.client_portal_v1 import router as client_portal_v1_router
from app.routers.client_notifications import router as client_notifications_router
from app.routers.legal import router as legal_router
from app.routers.notifications import router as notifications_router
from app.routers.client_vehicles import router as client_vehicles_router
from app.routers.commercial_layer import router as commercial_layer_router
from app.routers.internal.fleet import router as internal_fleet_router
from app.routers.internal.fuel_providers import router as internal_fuel_providers_router
from app.routers.internal.telegram import router as internal_telegram_router
from app.routers.helpdesk_webhooks import router as helpdesk_webhooks_router
from app.routers.portal import client_router as portal_client_router, partner_router as portal_partner_router
from app.routers.partner.marketplace_analytics import router as partner_marketplace_analytics_router
from app.routers.partner.marketplace_catalog import router as partner_marketplace_router
from app.routers.partner.marketplace_orders import router as partner_marketplace_orders_router
from app.routers.partner.marketplace_promotions import router as partner_marketplace_promotions_router
from app.routers.partner.marketplace_coupons import router as partner_marketplace_coupons_router
from app.routers.partner.marketplace_subscriptions import router as partner_marketplace_subscriptions_router
from app.routers.partner.service_bookings import router as partner_service_bookings_router
from app.routers.partner.edo import router as partner_edo_router
from app.routers.kpi import router as kpi_router
from app.routers.subscriptions_admin import router as subscriptions_admin_router
from app.routers.subscriptions_v1 import router as subscriptions_router
from app.routers.explain_v2 import router as explain_v2_router
from app.routers.cases import router as cases_router
from app.routers.integrations.edo_sbis import router as edo_sbis_router
from app.services.bootstrap import ensure_default_refs
from app.services.accounting_export.metrics import metrics as accounting_export_metrics
from app.services.billing_metrics import metrics as billing_metrics
from app.services.payout_metrics import metrics as payout_metrics
from app.services.integration_metrics import metrics as intake_metrics
from app.services.bi.metrics import metrics as bi_metrics
from app.services.audit_metrics import metrics as audit_metrics
from app.fastapi_utils import generate_unique_id, safe_include_router
from app.services.audit_signing import AuditSigningService, get_audit_signing_health, set_audit_signing_health
from app.services.fleet_metrics import metrics as fleet_metrics
from app.services.cases_metrics import metrics as cases_metrics
from app.services.reconciliation_metrics import metrics as reconciliation_metrics
from app.services.export_metrics import metrics as export_metrics
from app.services.email_metrics import metrics as email_metrics
from app.services.report_schedule_metrics import metrics as report_schedule_metrics
from app.services.notification_metrics import metrics as notification_metrics
from app.services.limits import (
    CheckAndReserveRequest,
    CheckAndReserveTaskResponse,
    LimitsTaskResponse,
    RecalcLimitsRequest,
    call_limits_check_and_reserve_sync,
    celery_app,
)
from app.services.posting_metrics import metrics as posting_metrics
from app.services.risk_adapter import metrics as risk_metrics
from app.services.risk_v5.hook import register_shadow_hook
from app.services.risk_v5.metrics import metrics as risk_v5_metrics
from app.models.email_outbox import EmailOutbox, EmailOutboxStatus
from app.models.export_jobs import ExportJob, ExportJobStatus


# Если есть отдельный роутер для чтения операций из БД – подключим его
try:
    from app.api.v1.endpoints.operations_read import router as operations_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    operations_router = None  # type: ignore

# Роутер транзакций поверх operations
try:
    from app.api.v1.endpoints.transactions import router as transactions_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    transactions_router = None  # type: ignore

# Роутер отчётов по биллингу
try:
    from app.api.v1.endpoints.reports_billing import router as reports_billing_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    reports_billing_router = None  # type: ignore

try:
    from app.api.v1.endpoints.intake import router as intake_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    intake_router = None  # type: ignore

try:
    from app.api.v1.endpoints.partners import router as partners_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    partners_router = None  # type: ignore

try:
    from app.api.v1.endpoints.billing_invoices import router as billing_invoices_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    billing_invoices_router = None  # type: ignore

try:
    from app.api.v1.endpoints.payouts import router as payouts_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    payouts_router = None  # type: ignore

try:
    from app.api.v1.endpoints.fuel_transactions import router as fuel_transactions_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    fuel_transactions_router = None  # type: ignore

try:
    from app.api.v1.endpoints.logistics import router as logistics_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    logistics_router = None  # type: ignore

try:
    from app.api.v1.endpoints.edo_events import router as edo_events_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    edo_events_router = None  # type: ignore

try:
    from app.api.v1.endpoints.bi import router as bi_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    bi_router = None  # type: ignore

try:
    from app.api.v1.endpoints.bi_dashboards import router as bi_dashboards_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    bi_dashboards_router = None  # type: ignore

try:
    from app.api.v1.endpoints.pricing_intelligence import router as pricing_intelligence_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    pricing_intelligence_router = None  # type: ignore

try:
    from app.api.v1.endpoints.support_requests import router as support_requests_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    support_requests_router = None  # type: ignore

SERVICE_NAME = os.getenv("SERVICE_NAME", "core-api")
DEFAULT_API_PREFIX = "/api/core"
LEGACY_API_PREFIX = "/api"
API_PREFIX_CORE = os.getenv("API_PREFIX_CORE", DEFAULT_API_PREFIX)
CORE_API_PREFIX = DEFAULT_API_PREFIX


def _normalize_api_prefix(prefix: str, default: str) -> str:
    if not prefix:
        return default
    normalized = prefix if prefix.startswith("/") else f"/{prefix}"
    return normalized.rstrip("/") or default


API_PREFIX_CORE = _normalize_api_prefix(API_PREFIX_CORE, DEFAULT_API_PREFIX)
INCLUDE_CORE_PREFIX_ROUTES = API_PREFIX_CORE != CORE_API_PREFIX
INCLUDE_API_PREFIX_CORE = API_PREFIX_CORE != LEGACY_API_PREFIX
INCLUDE_CUSTOM_CORE_PREFIX = INCLUDE_API_PREFIX_CORE and INCLUDE_CORE_PREFIX_ROUTES
init_logging(service_name=SERVICE_NAME)
logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Pydantic-модели
# -----------------------------------------------------------------------------
class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "ok"
    audit_signing: str | None = None
    audit_signing_mode: str | None = None


# -----------------------------------------------------------------------------
# FASTAPI
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    db = get_sessionmaker()()
    try:
        ensure_default_refs(db)
    finally:
        db.close()
    register_shadow_hook()
    signing_service = AuditSigningService()
    signing_status = "ok"
    if signing_service.required:
        signing_status = "ok" if signing_service.self_check() else "fail"
        if signing_status == "fail":
            set_audit_signing_health("fail")
            raise RuntimeError("Audit signing self-check failed")
    set_audit_signing_health(signing_status)
    logger.info("core-api startup complete")
    yield


app = FastAPI(
    title="NEFT Core API",
    version="0.1.0",
    lifespan=lifespan,
    generate_unique_id_function=generate_unique_id,
)


def custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["openapi"] = "3.0.3"
    for path_item in openapi_schema.get("paths", {}).values():
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if "requestBody" not in operation:
                operation["requestBody"] = {
                    "content": {
                        "application/json": {
                            "schema": {"type": "object"},
                        }
                    }
                }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Основной роутер v1
safe_include_router(app, api_router, prefix="/api/v1")

# Включаем доп. роутер с чтением операций из БД, если он есть
if operations_router is not None:
    safe_include_router(app, operations_router, prefix="")

# Включаем роутер транзакций, если он доступен
if transactions_router is not None:
    safe_include_router(app, transactions_router, prefix="")

# Включаем роутер отчётов, если он доступен
if reports_billing_router is not None:
    safe_include_router(app, reports_billing_router, prefix="")
if fuel_transactions_router is not None:
    safe_include_router(app, fuel_transactions_router, prefix="")
if logistics_router is not None:
    safe_include_router(app, logistics_router, prefix="")
if edo_events_router is not None:
    safe_include_router(app, edo_events_router, prefix="")
if bi_router is not None:
    safe_include_router(app, bi_router, prefix="")
if bi_dashboards_router is not None:
    safe_include_router(app, bi_dashboards_router, prefix="")
if pricing_intelligence_router is not None:
    safe_include_router(app, pricing_intelligence_router, prefix="")
if support_requests_router is not None:
    safe_include_router(app, support_requests_router, prefix="")

if intake_router is not None:
    safe_include_router(app, intake_router, prefix="")

if partners_router is not None:
    safe_include_router(app, partners_router, prefix="")
if billing_invoices_router is not None:
    safe_include_router(app, billing_invoices_router, prefix="")
if payouts_router is not None:
    safe_include_router(app, payouts_router, prefix="")

safe_include_router(app, admin_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, admin_router, prefix=API_PREFIX_CORE)
safe_include_router(app, legal_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, legal_router, prefix=API_PREFIX_CORE)
if INCLUDE_CORE_PREFIX_ROUTES:
    safe_include_router(app, kpi_router, prefix=API_PREFIX_CORE)
    safe_include_router(app, explain_v2_router, prefix=API_PREFIX_CORE)
    safe_include_router(app, cases_router, prefix=API_PREFIX_CORE)
    safe_include_router(app, achievements_router, prefix=API_PREFIX_CORE)
    safe_include_router(app, subscriptions_router, prefix=API_PREFIX_CORE)
    safe_include_router(app, subscriptions_admin_router, prefix=API_PREFIX_CORE)
safe_include_router(app, client_router)
if INCLUDE_CORE_PREFIX_ROUTES:
    safe_include_router(app, client_router, prefix=API_PREFIX_CORE)
if INCLUDE_CORE_PREFIX_ROUTES:
    safe_include_router(app, client_auth_gateway_router, prefix=API_PREFIX_CORE)
if INCLUDE_CORE_PREFIX_ROUTES:
    safe_include_router(app, admin_auth_gateway_router, prefix=API_PREFIX_CORE)
if INCLUDE_CORE_PREFIX_ROUTES:
    safe_include_router(app, client_me_router, prefix=API_PREFIX_CORE)
safe_include_router(app, notifications_router)
if INCLUDE_CORE_PREFIX_ROUTES:
    safe_include_router(app, notifications_router, prefix=API_PREFIX_CORE)
safe_include_router(app, fleet_router)
if INCLUDE_CORE_PREFIX_ROUTES:
    safe_include_router(app, fleet_router, prefix=API_PREFIX_CORE)
safe_include_router(app, client_portal_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, client_portal_router, prefix=API_PREFIX_CORE)
    safe_include_router(app, client_onboarding_router, prefix=API_PREFIX_CORE)
    safe_include_router(app, client_portal_v1_router, prefix=API_PREFIX_CORE)
safe_include_router(app, client_vehicles_router)
if INCLUDE_CORE_PREFIX_ROUTES:
    safe_include_router(app, client_vehicles_router, prefix=API_PREFIX_CORE)
safe_include_router(app, portal_client_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, portal_client_router, prefix=API_PREFIX_CORE)
safe_include_router(app, portal_partner_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, portal_partner_router, prefix=API_PREFIX_CORE)
safe_include_router(app, partner_marketplace_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, partner_marketplace_router, prefix=API_PREFIX_CORE)
safe_include_router(app, partner_marketplace_orders_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, partner_marketplace_orders_router, prefix=API_PREFIX_CORE)
safe_include_router(app, partner_marketplace_promotions_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, partner_marketplace_promotions_router, prefix=API_PREFIX_CORE)
safe_include_router(app, partner_marketplace_coupons_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, partner_marketplace_coupons_router, prefix=API_PREFIX_CORE)
safe_include_router(app, partner_marketplace_analytics_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, partner_marketplace_analytics_router, prefix=API_PREFIX_CORE)
safe_include_router(app, partner_marketplace_subscriptions_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, partner_marketplace_subscriptions_router, prefix=API_PREFIX_CORE)
safe_include_router(app, partner_service_bookings_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, partner_service_bookings_router, prefix=API_PREFIX_CORE)
safe_include_router(app, partner_edo_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, partner_edo_router, prefix=API_PREFIX_CORE)
safe_include_router(app, client_marketplace_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, client_marketplace_router, prefix=API_PREFIX_CORE)
safe_include_router(app, client_marketplace_orders_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, client_marketplace_orders_router, prefix=API_PREFIX_CORE)
safe_include_router(app, client_marketplace_deals_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, client_marketplace_deals_router, prefix=API_PREFIX_CORE)
safe_include_router(app, client_service_bookings_router, prefix=LEGACY_API_PREFIX)
if INCLUDE_CUSTOM_CORE_PREFIX:
    safe_include_router(app, client_service_bookings_router, prefix=API_PREFIX_CORE)
safe_include_router(app, client_documents_router)
if INCLUDE_CORE_PREFIX_ROUTES:
    safe_include_router(app, document_templates_router, prefix=API_PREFIX_CORE)
if INCLUDE_CORE_PREFIX_ROUTES:
    safe_include_router(app, legal_gate_router, prefix=API_PREFIX_CORE)
safe_include_router(app, internal_fleet_router)
safe_include_router(app, internal_fuel_providers_router)
safe_include_router(app, internal_telegram_router)
safe_include_router(app, commercial_layer_router)
safe_include_router(app, edo_sbis_router)

# Префиксированный роутер для нового gateway namespace /api/core/*
core_prefixed_router = APIRouter(prefix="/api/core")
safe_include_router(core_prefixed_router, api_router, prefix="/api/v1")

if operations_router is not None:
    safe_include_router(core_prefixed_router, operations_router, prefix="")
if transactions_router is not None:
    safe_include_router(core_prefixed_router, transactions_router, prefix="")
if reports_billing_router is not None:
    safe_include_router(core_prefixed_router, reports_billing_router, prefix="")
if fuel_transactions_router is not None:
    safe_include_router(core_prefixed_router, fuel_transactions_router, prefix="")
if logistics_router is not None:
    safe_include_router(core_prefixed_router, logistics_router, prefix="")
if edo_events_router is not None:
    safe_include_router(core_prefixed_router, edo_events_router, prefix="")
if bi_router is not None:
    safe_include_router(core_prefixed_router, bi_router, prefix="")
if bi_dashboards_router is not None:
    safe_include_router(core_prefixed_router, bi_dashboards_router, prefix="")
if pricing_intelligence_router is not None:
    safe_include_router(core_prefixed_router, pricing_intelligence_router, prefix="")
if support_requests_router is not None:
    safe_include_router(core_prefixed_router, support_requests_router, prefix="")
if intake_router is not None:
    safe_include_router(core_prefixed_router, intake_router, prefix="")
if partners_router is not None:
    safe_include_router(core_prefixed_router, partners_router, prefix="")
if billing_invoices_router is not None:
    safe_include_router(core_prefixed_router, billing_invoices_router, prefix="")
if payouts_router is not None:
    safe_include_router(core_prefixed_router, payouts_router, prefix="")

safe_include_router(core_prefixed_router, admin_router)
safe_include_router(core_prefixed_router, kpi_router)
safe_include_router(core_prefixed_router, explain_v2_router)
safe_include_router(core_prefixed_router, cases_router)
safe_include_router(core_prefixed_router, achievements_router)
safe_include_router(core_prefixed_router, subscriptions_router)
safe_include_router(core_prefixed_router, subscriptions_admin_router)
safe_include_router(core_prefixed_router, client_router)
safe_include_router(core_prefixed_router, client_auth_gateway_router)
safe_include_router(core_prefixed_router, admin_auth_gateway_router)
safe_include_router(core_prefixed_router, client_me_router)
safe_include_router(core_prefixed_router, client_portal_v1_router)
safe_include_router(core_prefixed_router, client_notifications_router)
safe_include_router(core_prefixed_router, fleet_router)
safe_include_router(core_prefixed_router, client_portal_router)
safe_include_router(core_prefixed_router, client_onboarding_router)
safe_include_router(core_prefixed_router, client_vehicles_router)
safe_include_router(core_prefixed_router, client_documents_router)
safe_include_router(core_prefixed_router, document_templates_router)
safe_include_router(core_prefixed_router, legal_gate_router)
safe_include_router(core_prefixed_router, client_service_completion_proofs_router)
safe_include_router(core_prefixed_router, internal_fleet_router)
safe_include_router(core_prefixed_router, internal_fuel_providers_router)
safe_include_router(core_prefixed_router, internal_telegram_router)
safe_include_router(core_prefixed_router, helpdesk_webhooks_router)
safe_include_router(core_prefixed_router, commercial_layer_router)
safe_include_router(core_prefixed_router, partner_edo_router)


# -----------------------------------------------------------------------------
# METRICS
# -----------------------------------------------------------------------------
def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * (pct / 100)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[int(k)]
    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f)
    return d0 + d1


def _format_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    parts = [f'{key}="{value}"' for key, value in labels.items()]
    return "{" + ",".join(parts) + "}"


def _render_histogram(
    *,
    metric_prefix: str,
    help_text: str,
    items: dict[tuple[str, ...], Any],
    label_names: list[str],
) -> list[str]:
    lines = [
        f"# HELP {metric_prefix} {help_text}",
        f"# TYPE {metric_prefix} histogram",
    ]
    if not items:
        lines.append(f'{metric_prefix}_bucket{{le="+Inf"}} 0')
        lines.append(f"{metric_prefix}_sum 0")
        lines.append(f"{metric_prefix}_count 0")
        return lines

    for key, histogram in items.items():
        labels = dict(zip(label_names, key, strict=False))
        bucket_counts = histogram.counts
        for bucket in histogram.buckets:
            bucket_labels = dict(labels)
            bucket_labels["le"] = str(bucket)
            lines.append(f"{metric_prefix}_bucket{_format_labels(bucket_labels)} {bucket_counts.get(bucket, 0)}")
        inf_labels = dict(labels)
        inf_labels["le"] = "+Inf"
        lines.append(f"{metric_prefix}_bucket{_format_labels(inf_labels)} {histogram.total_count}")
        lines.append(f"{metric_prefix}_sum{_format_labels(labels)} {histogram.total_sum}")
        lines.append(f"{metric_prefix}_count{_format_labels(labels)} {histogram.total_count}")
    return lines


def _billing_metrics() -> list[str]:
    lines = [
        "# HELP core_api_billing_generated_total Total invoices generated.",
        "# TYPE core_api_billing_generated_total counter",
        f"core_api_billing_generated_total {billing_metrics.generated_invoices_total}",
        "# HELP core_api_billing_last_run_generated Invoices generated in the last billing run.",
        "# TYPE core_api_billing_last_run_generated counter",
        f"core_api_billing_last_run_generated {billing_metrics.last_run_generated}",
        "# HELP core_api_billing_errors_total Billing errors encountered.",
        "# TYPE core_api_billing_errors_total counter",
        f"core_api_billing_errors_total {billing_metrics.billing_errors}",
        "# HELP core_api_billing_pdf_generated_total Invoice PDFs generated.",
        "# TYPE core_api_billing_pdf_generated_total counter",
        f"core_api_billing_pdf_generated_total {billing_metrics.pdf_generated_total}",
        "# HELP core_api_billing_pdf_errors_total Invoice PDF generation errors.",
        "# TYPE core_api_billing_pdf_errors_total counter",
        f"core_api_billing_pdf_errors_total {billing_metrics.pdf_errors_total}",
        "# HELP core_api_invoice_payments_total Total invoice payments by status.",
        "# TYPE core_api_invoice_payments_total counter",
        f'core_api_invoice_payments_total{{status="posted"}} {billing_metrics.invoice_payments_posted_total}',
        f'core_api_invoice_payments_total{{status="failed"}} {billing_metrics.invoice_payments_failed_total}',
        "# HELP core_api_invoice_payment_amount_total Total amount received via invoice payments.",
        "# TYPE core_api_invoice_payment_amount_total counter",
        f"core_api_invoice_payment_amount_total {billing_metrics.invoice_payment_amount_total}",
        "# HELP core_api_invoice_paid_total Total invoices marked as paid.",
        "# TYPE core_api_invoice_paid_total counter",
        f"core_api_invoice_paid_total {billing_metrics.invoice_paid_total}",
        "# HELP core_api_invoice_payment_errors_total Invoice payment errors.",
        "# TYPE core_api_invoice_payment_errors_total counter",
        f"core_api_invoice_payment_errors_total {billing_metrics.invoice_payment_errors_total}",
        "# HELP core_api_invoice_refunds_total Total invoice refunds posted.",
        "# TYPE core_api_invoice_refunds_total counter",
        f"core_api_invoice_refunds_total {billing_metrics.invoice_refunds_total}",
        "# HELP core_api_billing_amount_total Total billed amount per period.",
        "# TYPE core_api_billing_amount_total counter",
    ]
    for period, amount in billing_metrics.billed_amounts.items():
        lines.append(f'core_api_billing_amount_total{{period="{period}"}} {amount}')
    if not billing_metrics.billed_amounts:
        lines.append('core_api_billing_amount_total{period="unknown"} 0')

    lines.append("# HELP core_api_billing_daily_runs_total Total daily billing runs by status.")
    lines.append("# TYPE core_api_billing_daily_runs_total counter")
    if billing_metrics.daily_runs:
        for status, count in billing_metrics.daily_runs.items():
            lines.append(f'core_api_billing_daily_runs_total{{status="{status}"}} {count}')
    else:
        lines.append('core_api_billing_daily_runs_total{status="unset"} 0')

    lines.append("# HELP core_api_billing_finalize_runs_total Total finalize billing runs by status.")
    lines.append("# TYPE core_api_billing_finalize_runs_total counter")
    if billing_metrics.finalize_runs:
        for status, count in billing_metrics.finalize_runs.items():
            lines.append(f'core_api_billing_finalize_runs_total{{status="{status}"}} {count}')
    else:
        lines.append('core_api_billing_finalize_runs_total{status="unset"} 0')

    lines.append("# HELP core_api_billing_reconcile_runs_total Total reconciliation runs by status.")
    lines.append("# TYPE core_api_billing_reconcile_runs_total counter")
    if billing_metrics.reconcile_runs:
        for status, count in billing_metrics.reconcile_runs.items():
            lines.append(f'core_api_billing_reconcile_runs_total{{status="{status}"}} {count}')
    else:
        lines.append('core_api_billing_reconcile_runs_total{status="unset"} 0')

    lines.append("# HELP core_api_billing_last_run_duration_ms Last billing job duration in milliseconds.")
    lines.append("# TYPE core_api_billing_last_run_duration_ms gauge")
    if billing_metrics.last_run_duration_ms:
        for job, duration in billing_metrics.last_run_duration_ms.items():
            lines.append(f'core_api_billing_last_run_duration_ms{{job="{job}"}} {duration}')
    else:
        lines.append('core_api_billing_last_run_duration_ms{job="unset"} 0')
    return lines


def _payout_metrics() -> list[str]:
    export_state_lines = [
        f'core_api_payout_exports_total{{format="{export_format}",state="{state}"}} {count}'
        for (export_format, state), count in payout_metrics.exports_total.items()
    ]
    if not export_state_lines:
        export_state_lines.append('core_api_payout_exports_total{format="unset",state="unset"} 0')

    export_bytes_lines = [
        f'core_api_payout_export_bytes_total{{format="{export_format}"}} {count}'
        for export_format, count in payout_metrics.export_bytes_total.items()
    ]
    if not export_bytes_lines:
        export_bytes_lines.append('core_api_payout_export_bytes_total{format="unset"} 0')

    export_download_lines = [
        f'core_api_payout_export_download_total{{format="{export_format}"}} {count}'
        for export_format, count in payout_metrics.export_download_total.items()
    ]
    if not export_download_lines:
        export_download_lines.append('core_api_payout_export_download_total{format="unset"} 0')

    return [
        f"core_api_payout_batches_created_total {payout_metrics.batches_created_total}",
        f"core_api_payout_batches_errors_total {payout_metrics.batches_errors_total}",
        f"core_api_payout_batches_settled_total {payout_metrics.batches_settled_total}",
        f"core_api_payout_reconcile_mismatch_total {payout_metrics.reconcile_mismatch_total}",
        f"core_api_payout_amount_total {payout_metrics.payout_amount_total}",
        *export_state_lines,
        f"core_api_payout_export_errors_total {payout_metrics.export_errors_total}",
        *export_bytes_lines,
        *export_download_lines,
        f"core_api_payout_export_download_errors_total {payout_metrics.export_download_errors_total}",
    ]


def _bi_metrics() -> list[str]:
    ingest_lines = [
        f'core_api_bi_ingest_events_total{{status="{status}"}} {count}'
        for status, count in bi_metrics.ingest_events_total.items()
    ]
    if not ingest_lines:
        ingest_lines.append('core_api_bi_ingest_events_total{status="unset"} 0')

    aggregate_lines = [
        f'core_api_bi_aggregate_total{{status="{status}"}} {count}'
        for status, count in bi_metrics.aggregate_total.items()
    ]
    if not aggregate_lines:
        aggregate_lines.append('core_api_bi_aggregate_total{status="unset"} 0')

    export_lines = [
        f'core_api_bi_exports_total{{dataset="{dataset}",format="{export_format}",status="{status}"}} {count}'
        for (dataset, export_format, status), count in bi_metrics.exports_total.items()
    ]
    if not export_lines:
        export_lines.append('core_api_bi_exports_total{dataset="unset",format="unset",status="unset"} 0')

    clickhouse_lines = [
        f'core_api_bi_clickhouse_sync_total{{dataset="{dataset}",status="{status}"}} {count}'
        for (dataset, status), count in bi_metrics.clickhouse_sync_total.items()
    ]
    if not clickhouse_lines:
        clickhouse_lines.append('core_api_bi_clickhouse_sync_total{dataset="unset",status="unset"} 0')

    clickhouse_lag_lines = [
        f'core_api_bi_clickhouse_lag_seconds{{dataset="{dataset}"}} {lag}'
        for dataset, lag in bi_metrics.clickhouse_lag_seconds.items()
    ]
    if not clickhouse_lag_lines:
        clickhouse_lag_lines.append('core_api_bi_clickhouse_lag_seconds{dataset="unset"} 0')
    sync_duration = bi_metrics.sync_duration_seconds
    rows_written_total = bi_metrics.rows_written_total
    query_latency = bi_metrics.query_latency_seconds

    return [
        "# HELP core_api_bi_ingest_events_total BI ingest runs by status.",
        "# TYPE core_api_bi_ingest_events_total counter",
        *ingest_lines,
        "# HELP core_api_bi_ingest_lag_seconds BI ingest lag seconds.",
        "# TYPE core_api_bi_ingest_lag_seconds gauge",
        f"core_api_bi_ingest_lag_seconds {bi_metrics.ingest_lag_seconds}",
        "# HELP core_api_bi_aggregate_total BI aggregation runs by status.",
        "# TYPE core_api_bi_aggregate_total counter",
        *aggregate_lines,
        "# HELP core_api_bi_exports_total BI exports by dataset/format/status.",
        "# TYPE core_api_bi_exports_total counter",
        *export_lines,
        "# HELP core_api_bi_export_generate_duration_seconds BI export generation duration seconds.",
        "# TYPE core_api_bi_export_generate_duration_seconds gauge",
        f"core_api_bi_export_generate_duration_seconds {bi_metrics.export_generate_duration_seconds}",
        "# HELP core_api_bi_clickhouse_sync_total BI ClickHouse sync by dataset/status.",
        "# TYPE core_api_bi_clickhouse_sync_total counter",
        *clickhouse_lines,
        "# HELP core_api_bi_clickhouse_lag_seconds BI ClickHouse lag seconds.",
        "# TYPE core_api_bi_clickhouse_lag_seconds gauge",
        *clickhouse_lag_lines,
        "# HELP core_api_bi_sync_duration_seconds BI sync duration seconds.",
        "# TYPE core_api_bi_sync_duration_seconds gauge",
        f"core_api_bi_sync_duration_seconds {sync_duration}",
        "# HELP core_api_bi_rows_written_total BI rows written total.",
        "# TYPE core_api_bi_rows_written_total counter",
        f"core_api_bi_rows_written_total {rows_written_total}",
        "# HELP core_api_bi_query_latency_seconds BI query latency seconds.",
        "# TYPE core_api_bi_query_latency_seconds gauge",
        f"core_api_bi_query_latency_seconds {query_latency}",
    ]


def _reconciliation_metrics() -> list[str]:
    lines = [
        "# HELP core_api_reconciliation_runs_total Total reconciliation runs by scope/status.",
        "# TYPE core_api_reconciliation_runs_total counter",
    ]
    if reconciliation_metrics.runs_total:
        for key, count in reconciliation_metrics.runs_total.items():
            scope, status = key.split(":", maxsplit=1)
            lines.append(f'core_api_reconciliation_runs_total{{scope=\"{scope}\",status=\"{status}\"}} {count}')
    else:
        lines.append('core_api_reconciliation_runs_total{scope="unset",status="unset"} 0')

    lines.append("# HELP core_api_reconciliation_discrepancies_total Total discrepancies by type/status.")
    lines.append("# TYPE core_api_reconciliation_discrepancies_total counter")
    if reconciliation_metrics.discrepancies_total:
        for key, count in reconciliation_metrics.discrepancies_total.items():
            dtype, status = key.split(":", maxsplit=1)
            lines.append(
                f'core_api_reconciliation_discrepancies_total{{type=\"{dtype}\",status=\"{status}\"}} {count}'
            )
    else:
        lines.append('core_api_reconciliation_discrepancies_total{type="unset",status="unset"} 0')

    lines.extend(
        [
            "# HELP core_api_reconciliation_resolved_total Total resolved discrepancies.",
            "# TYPE core_api_reconciliation_resolved_total counter",
            f"core_api_reconciliation_resolved_total {reconciliation_metrics.resolved_total}",
            "# HELP core_api_reconciliation_total_delta_abs Total absolute delta across discrepancies.",
            "# TYPE core_api_reconciliation_total_delta_abs gauge",
            f"core_api_reconciliation_total_delta_abs {reconciliation_metrics.total_delta_abs}",
        ]
    )
    return lines


def _posting_metrics() -> list[str]:
    latency_p99 = _percentile(posting_metrics.latencies_ms, 99) or 0
    status_lines = [
        f'core_api_postings_status_total{{status="{status}"}} {count}'
        for status, count in posting_metrics.status_distribution.items()
    ]
    if not status_lines:
        status_lines.append('core_api_postings_status_total{status="unset"} 0')

    return [
        "# HELP core_api_postings_success_total Successful postings.",
        "# TYPE core_api_postings_success_total counter",
        f"core_api_postings_success_total {posting_metrics.successful_postings}",
        "# HELP core_api_postings_failed_total Failed postings.",
        "# TYPE core_api_postings_failed_total counter",
        f"core_api_postings_failed_total {posting_metrics.failed_postings}",
        "# HELP core_api_postings_contractual_declines_total Contractual declines encountered.",
        "# TYPE core_api_postings_contractual_declines_total counter",
        f"core_api_postings_contractual_declines_total {posting_metrics.contractual_declines}",
        "# HELP core_api_postings_status_total Posting status distribution.",
        "# TYPE core_api_postings_status_total counter",
        *status_lines,
        "# HELP core_api_postings_latency_p99_ms 99th percentile posting latency (ms).",
        "# TYPE core_api_postings_latency_p99_ms gauge",
        f"core_api_postings_latency_p99_ms {latency_p99}",
    ]


def _intake_metrics() -> list[str]:
    request_lines = [
        f'core_api_intake_requests_total{{name="{name}"}} {count}'
        for name, count in intake_metrics.intake_requests.items()
    ]
    if not request_lines:
        request_lines.append('core_api_intake_requests_total{name="unset"} 0')

    response_lines = [
        f'core_api_intake_responses_total{{status="{status}"}} {count}'
        for status, count in intake_metrics.responses.items()
    ]
    if not response_lines:
        response_lines.append('core_api_intake_responses_total{status="unset"} 0')

    return [
        "# HELP core_api_intake_requests_total Intake requests by name.",
        "# TYPE core_api_intake_requests_total counter",
        *request_lines,
        "# HELP core_api_intake_partner_errors_total Partner errors encountered.",
        "# TYPE core_api_intake_partner_errors_total counter",
        f"core_api_intake_partner_errors_total {intake_metrics.partner_errors}",
        "# HELP core_api_intake_posting_errors_total Posting errors encountered during intake.",
        "# TYPE core_api_intake_posting_errors_total counter",
        f"core_api_intake_posting_errors_total {intake_metrics.posting_errors}",
        "# HELP core_api_intake_responses_total Intake responses by status.",
        "# TYPE core_api_intake_responses_total counter",
        *response_lines,
    ]


def _audit_metrics() -> list[str]:
    event_lines = [
        f"core_api_audit_events_total{{event_type='{event_type}'}} {count}"
        for event_type, count in audit_metrics.events_total.items()
    ]
    if not event_lines:
        event_lines.append('core_api_audit_events_total{event_type="unset"} 0')

    return [
        "# HELP core_api_audit_events_total Total audit events by type.",
        "# TYPE core_api_audit_events_total counter",
        *event_lines,
        "# HELP core_api_audit_write_errors_total Audit write errors.",
        "# TYPE core_api_audit_write_errors_total counter",
        f"core_api_audit_write_errors_total {audit_metrics.write_errors_total}",
        "# HELP core_api_audit_verify_broken_total Audit chain verification failures.",
        "# TYPE core_api_audit_verify_broken_total counter",
        f"core_api_audit_verify_broken_total {audit_metrics.verify_broken_total}",
    ]


def _cases_metrics() -> list[str]:
    escalation_lines = [
        f'core_api_cases_escalations_total{{level="{level}"}} {count}'
        for level, count in cases_metrics.escalations_total.items()
    ]
    if not escalation_lines:
        escalation_lines.append('core_api_cases_escalations_total{level="unset"} 0')

    breach_lines = [
        f'core_api_cases_sla_breaches_total{{kind="{kind}"}} {count}'
        for kind, count in cases_metrics.sla_breaches_total.items()
    ]
    if not breach_lines:
        breach_lines.append('core_api_cases_sla_breaches_total{kind="unset"} 0')

    support_breach_lines = [
        f'support_sla_breaches_total{{kind="{kind}"}} {count}'
        for kind, count in cases_metrics.sla_breaches_total.items()
    ]
    if not support_breach_lines:
        support_breach_lines.append('support_sla_breaches_total{kind="unset"} 0')

    support_created_lines = [
        f'support_tickets_created_total{{priority="{priority}"}} {count}'
        for priority, count in cases_metrics.support_tickets_created_total.items()
    ]
    if not support_created_lines:
        support_created_lines.append('support_tickets_created_total{priority="unset"} 0')

    return [
        "# HELP core_api_cases_escalations_total Total SLA escalations by level.",
        "# TYPE core_api_cases_escalations_total counter",
        *escalation_lines,
        "# HELP core_api_cases_sla_breaches_total Total SLA breaches by kind.",
        "# TYPE core_api_cases_sla_breaches_total counter",
        *breach_lines,
        "# HELP support_sla_breaches_total Support SLA breaches by kind.",
        "# TYPE support_sla_breaches_total counter",
        *support_breach_lines,
        "# HELP support_tickets_created_total Support tickets created by priority.",
        "# TYPE support_tickets_created_total counter",
        *support_created_lines,
        "# HELP support_tickets_closed_total Support tickets closed.",
        "# TYPE support_tickets_closed_total counter",
        f"support_tickets_closed_total {cases_metrics.support_tickets_closed_total}",
    ]


def _export_job_metrics() -> list[str]:
    created_lines = [
        f'export_jobs_created_total{{report_type="{report_type}",format="{export_format}"}} {count}'
        for (report_type, export_format), count in export_metrics.created_total.items()
    ]
    if not created_lines:
        created_lines.append('export_jobs_created_total{report_type="unset",format="unset"} 0')

    completed_lines = [
        f'export_jobs_completed_total{{report_type="{report_type}",format="{export_format}",status="{status}"}} {count}'
        for (report_type, export_format, status), count in export_metrics.completed_total.items()
    ]
    if not completed_lines:
        completed_lines.append('export_jobs_completed_total{report_type="unset",format="unset",status="unset"} 0')

    failure_lines = [
        f'export_job_failures_total{{reason="{reason}"}} {count}'
        for reason, count in export_metrics.failures_total.items()
    ]
    if not failure_lines:
        failure_lines.append('export_job_failures_total{reason="unset"} 0')

    lines = [
        "# HELP export_jobs_created_total Export jobs created.",
        "# TYPE export_jobs_created_total counter",
        *created_lines,
        "# HELP export_jobs_completed_total Export jobs completed.",
        "# TYPE export_jobs_completed_total counter",
        *completed_lines,
    ]
    lines.extend(
        _render_histogram(
            metric_prefix="export_job_duration_seconds",
            help_text="Export job duration seconds.",
            items=export_metrics.duration_seconds,
            label_names=["report_type", "format"],
        )
    )
    lines.extend(
        _render_histogram(
            metric_prefix="export_job_rows",
            help_text="Export job row counts.",
            items=export_metrics.rows,
            label_names=["report_type", "format"],
        )
    )
    lines.extend(
        [
            "# HELP export_job_failures_total Export job failures by reason.",
            "# TYPE export_job_failures_total counter",
            *failure_lines,
        ]
    )
    return lines


def _email_outbox_metrics() -> list[str]:
    enqueued_lines = [
        f'email_outbox_enqueued_total{{template_key="{template_key}"}} {count}'
        for template_key, count in email_metrics.enqueued_total.items()
    ]
    if not enqueued_lines:
        enqueued_lines.append('email_outbox_enqueued_total{template_key="unset"} 0')

    sent_lines = [
        f'email_outbox_sent_total{{provider="{provider}"}} {count}'
        for provider, count in email_metrics.sent_total.items()
    ]
    if not sent_lines:
        sent_lines.append('email_outbox_sent_total{provider="unset"} 0')

    failed_lines = [
        f'email_outbox_failed_total{{provider="{provider}",reason="{reason}"}} {count}'
        for (provider, reason), count in email_metrics.failed_total.items()
    ]
    if not failed_lines:
        failed_lines.append('email_outbox_failed_total{provider="unset",reason="unset"} 0')

    lines = [
        "# HELP email_outbox_enqueued_total Emails enqueued by template.",
        "# TYPE email_outbox_enqueued_total counter",
        *enqueued_lines,
        "# HELP email_outbox_sent_total Emails sent by provider.",
        "# TYPE email_outbox_sent_total counter",
        *sent_lines,
        "# HELP email_outbox_failed_total Email failures by provider and reason.",
        "# TYPE email_outbox_failed_total counter",
        *failed_lines,
    ]
    lines.extend(
        _render_histogram(
            metric_prefix="email_delivery_duration_seconds",
            help_text="Email delivery duration seconds.",
            items={(provider,): histogram for provider, histogram in email_metrics.delivery_duration_seconds.items()},
            label_names=["provider"],
        )
    )
    return lines


def _report_schedule_metrics() -> list[str]:
    triggered_lines = [
        f'report_schedules_triggered_total{{report_type="{report_type}",format="{export_format}"}} {count}'
        for (report_type, export_format), count in report_schedule_metrics.triggered_total.items()
    ]
    if not triggered_lines:
        triggered_lines.append('report_schedules_triggered_total{report_type="unset",format="unset"} 0')

    skipped_lines = [
        f'report_schedules_skipped_total{{reason="{reason}"}} {count}'
        for reason, count in report_schedule_metrics.skipped_total.items()
    ]
    if not skipped_lines:
        skipped_lines.append('report_schedules_skipped_total{reason="unset"} 0')

    lines = [
        "# HELP report_schedules_triggered_total Report schedules triggered.",
        "# TYPE report_schedules_triggered_total counter",
        *triggered_lines,
        "# HELP report_schedules_skipped_total Report schedules skipped.",
        "# TYPE report_schedules_skipped_total counter",
        *skipped_lines,
    ]
    lines.extend(
        _render_histogram(
            metric_prefix="report_schedule_trigger_lag_seconds",
            help_text="Report schedule trigger lag seconds.",
            items={(): report_schedule_metrics.trigger_lag_seconds},
            label_names=[],
        )
    )
    return lines


def _notification_metrics() -> list[str]:
    created_lines = [
        f'client_notifications_created_total{{type="{event_type}",severity="{severity}"}} {count}'
        for (event_type, severity), count in notification_metrics.created_total.items()
    ]
    if not created_lines:
        created_lines.append('client_notifications_created_total{type="unset",severity="unset"} 0')
    return [
        "# HELP client_notifications_created_total Client notifications created.",
        "# TYPE client_notifications_created_total counter",
        *created_lines,
    ]


def _queue_metrics() -> list[str]:
    session = get_sessionmaker()()
    try:
        outbox_backlog = (
            session.query(EmailOutbox).filter(EmailOutbox.status == EmailOutboxStatus.QUEUED).count()
        )
        running_started_at = (
            session.query(ExportJob.started_at)
            .filter(ExportJob.status == ExportJobStatus.RUNNING)
            .order_by(ExportJob.started_at.asc())
            .limit(1)
            .scalar()
        )
        running_age_seconds = 0.0
        if running_started_at:
            running_age_seconds = max(0.0, (datetime.now(timezone.utc) - running_started_at).total_seconds())
        return [
            "# HELP email_outbox_backlog Email outbox backlog (queued).",
            "# TYPE email_outbox_backlog gauge",
            f"email_outbox_backlog {outbox_backlog}",
            "# HELP export_jobs_running_age_seconds Oldest running export job age in seconds.",
            "# TYPE export_jobs_running_age_seconds gauge",
            f"export_jobs_running_age_seconds {running_age_seconds}",
        ]
    except Exception:  # noqa: BLE001
        logger.exception("metrics_queue_collection_failed")
        return [
            "# HELP email_outbox_backlog Email outbox backlog (queued).",
            "# TYPE email_outbox_backlog gauge",
            "email_outbox_backlog 0",
            "# HELP export_jobs_running_age_seconds Oldest running export job age in seconds.",
            "# TYPE export_jobs_running_age_seconds gauge",
            "export_jobs_running_age_seconds 0",
        ]
    finally:
        session.close()


def _fleet_metrics() -> list[str]:
    lines: list[str] = []
    if fleet_metrics.ingest_jobs_total:
        for (status, provider), count in fleet_metrics.ingest_jobs_total.items():
            lines.append(f'core_api_fleet_ingest_jobs_total{{status="{status}",provider="{provider}"}} {count}')
    if fleet_metrics.ingest_items_total:
        for result, count in fleet_metrics.ingest_items_total.items():
            lines.append(f'core_api_fleet_ingest_items_total{{result="{result}"}} {count}')
    if fleet_metrics.limit_breaches_total:
        for (breach_type, scope), count in fleet_metrics.limit_breaches_total.items():
            lines.append(f'core_api_fleet_limit_breaches_total{{type="{breach_type}",scope="{scope}"}} {count}')
    if fleet_metrics.anomalies_total:
        for (anomaly_type, severity), count in fleet_metrics.anomalies_total.items():
            lines.append(f'core_api_fleet_anomalies_total{{type="{anomaly_type}",severity="{severity}"}} {count}')
    if fleet_metrics.notifications_outbox_total:
        for (status, event_type), count in fleet_metrics.notifications_outbox_total.items():
            lines.append(f'core_api_fleet_notifications_outbox_total{{status="{status}",event_type="{event_type}"}} {count}')
    if fleet_metrics.notifications_delivery_seconds:
        for channel, values in fleet_metrics.notifications_delivery_seconds.items():
            p95 = _percentile(values, 95) or 0
            lines.append(f'core_api_fleet_notifications_delivery_seconds{{channel="{channel}"}} {p95}')
    if fleet_metrics.webhook_responses_total:
        for status_bucket, count in fleet_metrics.webhook_responses_total.items():
            lines.append(f'core_api_fleet_webhook_responses_total{{status_bucket="{status_bucket}"}} {count}')
    lines.append(f"core_api_fleet_push_subscriptions_gauge {fleet_metrics.push_subscriptions_gauge}")
    if fleet_metrics.auto_actions_total:
        for (action, status), count in fleet_metrics.auto_actions_total.items():
            lines.append(f'core_api_fleet_auto_actions_total{{action="{action}",status="{status}"}} {count}')
    lines.append(f"core_api_fleet_alerts_open_gauge {fleet_metrics.alerts_open_gauge}")
    lines.append(f"core_api_fleet_transactions_total {fleet_metrics.transactions_total}")
    lines.append(f"core_api_fleet_export_requests_total {fleet_metrics.export_requests_total}")
    return lines

def _accounting_export_metrics() -> list[str]:
    return [
        "# HELP core_api_accounting_export_overdue_total Accounting export batches overdue for generation.",
        "# TYPE core_api_accounting_export_overdue_total counter",
        f"core_api_accounting_export_overdue_total {accounting_export_metrics.overdue_batches_total}",
        "# HELP core_api_accounting_export_unconfirmed_total Accounting export batches overdue for confirmation.",
        "# TYPE core_api_accounting_export_unconfirmed_total counter",
        f"core_api_accounting_export_unconfirmed_total {accounting_export_metrics.unconfirmed_batches_total}",
    ]


def _risk_metrics() -> list[str]:
    latency_p95 = _percentile(risk_metrics.latencies_ms, 95) or 0
    connection_lines = [
        f'core_api_risk_connection_errors_total{{kind="{kind}"}} {count}'
        for kind, count in risk_metrics.connection_errors.items()
    ]
    if not connection_lines:
        connection_lines.append('core_api_risk_connection_errors_total{kind="unset"} 0')

    score_lines = [
        f'core_api_risk_score_distribution_total{{bucket="{bucket}"}} {count}'
        for bucket, count in risk_metrics.score_distribution.items()
    ]
    if not score_lines:
        score_lines.append('core_api_risk_score_distribution_total{bucket="unset"} 0')

    return [
        "# HELP core_api_risk_latency_p95_ms 95th percentile latency for risk evaluations (ms).",
        "# TYPE core_api_risk_latency_p95_ms gauge",
        f"core_api_risk_latency_p95_ms {latency_p95}",
        "# HELP core_api_risk_connection_errors_total Connection errors when calling risk service.",
        "# TYPE core_api_risk_connection_errors_total counter",
        *connection_lines,
        "# HELP core_api_risk_score_distribution_total Distribution of risk scores by bucket.",
        "# TYPE core_api_risk_score_distribution_total counter",
        *score_lines,
    ]


def _risk_v5_metrics() -> list[str]:
    lines: list[str] = []
    disagreement = 0.0
    if risk_v5_metrics.total:
        disagreement = risk_v5_metrics.disagreement_total / max(risk_v5_metrics.total, 1)
    label_rate = 0.0
    if risk_v5_metrics.label_total:
        label_rate = risk_v5_metrics.label_available / max(risk_v5_metrics.label_total, 1)
    lines.extend(
        [
            "# HELP core_api_risk_v5_total Total v5 shadow decisions.",
            "# TYPE core_api_risk_v5_total counter",
            f"core_api_risk_v5_total {risk_v5_metrics.total}",
            "# HELP core_api_risk_v5_scored_total Total v5 shadow decisions with scores.",
            "# TYPE core_api_risk_v5_scored_total counter",
            f"core_api_risk_v5_scored_total {risk_v5_metrics.scored_total}",
            "# HELP core_api_risk_v5_disagreement_rate Disagreement rate between v4 and v5.",
            "# TYPE core_api_risk_v5_disagreement_rate gauge",
            f"core_api_risk_v5_disagreement_rate {disagreement}",
            "# HELP core_api_risk_v5_label_rate Share of shadow decisions with labels.",
            "# TYPE core_api_risk_v5_label_rate gauge",
            f"core_api_risk_v5_label_rate {label_rate}",
        ]
    )
    for bucket, count in risk_v5_metrics.score_distribution.items():
        lines.append(f'core_api_risk_v5_score_distribution_total{{bucket="{bucket}"}} {count}')
    for outcome, count in risk_v5_metrics.predicted_outcomes.items():
        lines.append(f'core_api_risk_v5_predicted_outcomes_total{{outcome="{outcome}"}} {count}')
    if not risk_v5_metrics.score_distribution:
        lines.append('core_api_risk_v5_score_distribution_total{bucket="unset"} 0')
    if not risk_v5_metrics.predicted_outcomes:
        lines.append('core_api_risk_v5_predicted_outcomes_total{outcome="unset"} 0')
    return lines


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:  # pragma: no cover - response verified via API test
    lines = [
        "# HELP core_api_up Core API availability.",
        "# TYPE core_api_up gauge",
        "core_api_up 1",
    ]
    lines.extend(_billing_metrics())
    lines.extend(_payout_metrics())
    lines.extend(_posting_metrics())
    lines.extend(_intake_metrics())
    lines.extend(_risk_metrics())
    lines.extend(_risk_v5_metrics())
    lines.extend(_audit_metrics())
    lines.extend(_cases_metrics())
    lines.extend(_export_job_metrics())
    lines.extend(_email_outbox_metrics())
    lines.extend(_report_schedule_metrics())
    lines.extend(_notification_metrics())
    lines.extend(_queue_metrics())
    lines.extend(_accounting_export_metrics())
    lines.extend(_fleet_metrics())
    lines.extend(_bi_metrics())
    lines.extend(_reconciliation_metrics())
    return "\n".join(lines) + "\n"


core_prefixed_router.add_api_route(
    "/metrics",
    metrics,
    response_class=PlainTextResponse,
    methods=["GET"],
)


@app.get("/metric", response_class=PlainTextResponse, include_in_schema=False)
def metric_alias() -> str:  # pragma: no cover - compatibility alias
    """Backward-compatible alias for the metrics endpoint."""

    return metrics()


# -----------------------------------------------------------------------------
# HEALTH
# -----------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse, response_model_exclude_none=True)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/health/db", response_model=HealthResponse, response_model_exclude_none=True)
def health_db(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        db.execute("SELECT 1")
        return HealthResponse(status="ok")
    except Exception as exc:  # pragma: no cover
        logger.exception("DB health failed: %s", exc)
        raise HTTPException(status_code=503, detail="db unavailable")


@app.get("/health/celery", response_model=HealthResponse, response_model_exclude_none=True)
def health_celery() -> HealthResponse:
    if not celery_app:
        raise HTTPException(status_code=503, detail="celery disabled")
    try:
        celery_app.control.ping(timeout=2)
        return HealthResponse(status="ok")
    except Exception as exc:  # pragma: no cover
        logger.exception("Celery health failed: %s", exc)
        raise HTTPException(status_code=503, detail="celery unavailable")


core_prefixed_router.add_api_route(
    "/health",
    health,
    response_model=HealthResponse,
    response_model_exclude_none=True,
    methods=["GET"],
)
core_prefixed_router.add_api_route(
    "/health/db",
    health_db,
    response_model=HealthResponse,
    response_model_exclude_none=True,
    methods=["GET"],
)
core_prefixed_router.add_api_route(
    "/health/celery",
    health_celery,
    response_model=HealthResponse,
    response_model_exclude_none=True,
    methods=["GET"],
)

safe_include_router(app, core_prefixed_router)


def _enforce_unique_routes(fastapi_app: FastAPI) -> None:
    duplicates: dict[tuple[str, str], list[APIRoute]] = defaultdict(list)
    seen: dict[tuple[str, str], APIRoute] = {}
    ignored_methods = {"HEAD", "OPTIONS"}
    for route in fastapi_app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = {method for method in (route.methods or set()) if method not in ignored_methods}
        for method in methods:
            key = (method, route.path)
            if key in seen:
                if not duplicates[key]:
                    duplicates[key].append(seen[key])
                duplicates[key].append(route)
            else:
                seen[key] = route

    if not duplicates:
        return

    lines = ["Duplicate routes detected:"]
    for (method, path), routes in sorted(duplicates.items()):
        names = ", ".join(sorted({route.name for route in routes}))
        lines.append(f"{method} {path} -> {names}")
    message = "\n".join(lines)
    logger.error(message)
    raise RuntimeError(message)


if API_PREFIX_CORE != CORE_API_PREFIX:
    app.add_api_route(
        f"{API_PREFIX_CORE}/health",
        health,
        response_model=HealthResponse,
        response_model_exclude_none=True,
        methods=["GET"],
    )

if os.getenv("NEFT_STRICT_ROUTES", "").lower() in {"1", "true", "yes"}:
    _enforce_unique_routes(app)


@app.get("/api/core/openapi.json", include_in_schema=False)
def core_prefixed_openapi() -> dict[str, Any]:
    return app.openapi()


@app.get("/api/core/docs", include_in_schema=False)
def core_prefixed_docs():
    return get_swagger_ui_html(openapi_url="/api/core/openapi.json", title="NEFT Core API")


# -----------------------------------------------------------------------------
# LIMITS – обёртки над tasks limits.check_and_reserve / limits.recalc
# -----------------------------------------------------------------------------
@app.post("/api/v1/limits/check-and-reserve", response_model=CheckAndReserveTaskResponse)
def limits_check_and_reserve(
    body: CheckAndReserveRequest = Body(...),
) -> CheckAndReserveTaskResponse:
    result = call_limits_check_and_reserve_sync(body)
    return CheckAndReserveTaskResponse(task="limits.check_and_reserve", result=result)


@app.post("/api/v1/limits/recalc", response_model=LimitsTaskResponse)
def limits_recalc(
    body: RecalcLimitsRequest = Body(...),
) -> LimitsTaskResponse:
    if not celery_app:
        return LimitsTaskResponse(
            task="limits.recalc",
            result={"status": "queued", "celery": "disabled"},
        )

    async_result = celery_app.send_task("limits.recalc_all", kwargs={})
    return LimitsTaskResponse(task="limits.recalc_all", result={"task_id": async_result.id})
