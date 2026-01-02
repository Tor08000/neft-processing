from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import uuid4

from celery.exceptions import TimeoutError as CeleryTimeoutError
from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import PlainTextResponse
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
from app.routers.client_portal import router as client_portal_router
from app.routers.internal.fleet import router as internal_fleet_router
from app.routers.portal import client_router as portal_client_router, partner_router as portal_partner_router
from app.routers.kpi import router as kpi_router
from app.routers.subscriptions_admin import router as subscriptions_admin_router
from app.routers.subscriptions_v1 import router as subscriptions_router
from app.routers.explain_v2 import router as explain_v2_router
from app.routers.cases import router as cases_router
from app.services.bootstrap import ensure_default_refs
from app.services.accounting_export.metrics import metrics as accounting_export_metrics
from app.services.billing_metrics import metrics as billing_metrics
from app.services.payout_metrics import metrics as payout_metrics
from app.services.integration_metrics import metrics as intake_metrics
from app.services.bi.metrics import metrics as bi_metrics
from app.services.audit_metrics import metrics as audit_metrics
from app.services.fleet_metrics import metrics as fleet_metrics
from app.services.cases_metrics import metrics as cases_metrics
from app.services.reconciliation_metrics import metrics as reconciliation_metrics
from app.services.limits import (
    CheckAndReserveRequest,
    CheckAndReserveResult,
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


def _normalize_api_prefix(prefix: str, default: str) -> str:
    if not prefix:
        return default
    normalized = prefix if prefix.startswith("/") else f"/{prefix}"
    return normalized.rstrip("/") or default


API_PREFIX_CORE = _normalize_api_prefix(API_PREFIX_CORE, DEFAULT_API_PREFIX)
init_logging(service_name=SERVICE_NAME)
logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Pydantic-модели
# -----------------------------------------------------------------------------
class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "ok"


class CeleryPingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str
    result: Dict[str, Any]


class TransactionLogEntry(BaseModel):
    operation_id: str
    created_at: datetime
    operation_type: str  # AUTH, CAPTURE, REFUND, REVERSAL
    status: str

    merchant_id: str
    terminal_id: str
    client_id: str
    card_id: str

    amount: int
    currency: str = "RUB"

    daily_limit: Optional[int] = None
    limit_per_tx: Optional[int] = None
    used_today: Optional[int] = None
    new_used_today: Optional[int] = None

    authorized: bool = False
    response_code: str = "00"
    response_message: str = "OK"

    parent_operation_id: Optional[str] = None
    reason: Optional[str] = None

    mcc: Optional[str] = None
    product_code: Optional[str] = None
    product_category: Optional[str] = None
    tx_type: Optional[str] = None


class TransactionsPage(BaseModel):
    items: List[TransactionLogEntry]
    total: int
    limit: int
    offset: int


class TerminalAuthRequest(BaseModel):
    merchant_id: str
    terminal_id: str
    client_id: str
    card_id: str
    amount: int
    currency: str = "RUB"
    product_code: Optional[str] = None
    product_category: Optional[str] = None
    mcc: Optional[str] = None
    tx_type: Optional[str] = None
    client_group_id: Optional[str] = None
    card_group_id: Optional[str] = None


class CaptureRequest(BaseModel):
    amount: int


class RefundRequest(BaseModel):
    # amount стал НЕобязательным:
    # - если есть → частичный / явный возврат
    # - если нет → FULL REFUND оставшейся суммы
    amount: Optional[int] = None
    reason: Optional[str] = None


class ReversalRequest(BaseModel):
    reason: Optional[str] = None


# -----------------------------------------------------------------------------
# In-memory лог операций + сохранение в БД
# -----------------------------------------------------------------------------
TRANSACTION_LOG: List[TransactionLogEntry] = []


def _persist_operation_to_db(entry: TransactionLogEntry) -> None:
    """
    Пишем операцию в таблицу operations через ORM.

    Используем каноническую модель app.models.operation.Operation.
    """
    try:
        from app.db import get_sessionmaker  # type: ignore
        from app.models.operation import Operation  # type: ignore
    except Exception as exc:  # pragma: no cover
        logger.warning("DB Operation model not available yet: %s", exc)
        return

    db = get_sessionmaker()()
    try:
        db_op = Operation(
            operation_id=entry.operation_id,
            created_at=entry.created_at,
            operation_type=entry.operation_type,
            status=entry.status,
            merchant_id=entry.merchant_id,
            terminal_id=entry.terminal_id,
            client_id=entry.client_id,
            card_id=entry.card_id,
            amount=entry.amount,
            currency=entry.currency,
            daily_limit=entry.daily_limit,
            limit_per_tx=entry.limit_per_tx,
            used_today=entry.used_today,
            new_used_today=entry.new_used_today,
            authorized=entry.authorized,
            response_code=entry.response_code,
            response_message=entry.response_message,
            parent_operation_id=entry.parent_operation_id,
            reason=entry.reason,
            mcc=entry.mcc,
            product_code=entry.product_code,
            product_category=entry.product_category,
            tx_type=entry.tx_type,
        )
        db.add(db_op)
        db.commit()
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to persist operation to DB: %s", exc)
        db.rollback()
    finally:
        db.close()


def _append_log_entry(entry: TransactionLogEntry) -> TransactionLogEntry:
    TRANSACTION_LOG.append(entry)
    _persist_operation_to_db(entry)
    return entry


def _find_transaction(operation_id: str) -> Optional[TransactionLogEntry]:
    for tx in TRANSACTION_LOG:
        if tx.operation_id == operation_id:
            return tx
    return None


def _get_transaction_or_404(operation_id: str) -> TransactionLogEntry:
    tx = _find_transaction(operation_id)
    if not tx:
        raise HTTPException(status_code=404, detail="operation not found")
    return tx


def _get_children(parent_id: str) -> List[TransactionLogEntry]:
    return [tx for tx in TRANSACTION_LOG if tx.parent_operation_id == parent_id]


def _get_captures_for_auth(auth_operation_id: str) -> List[TransactionLogEntry]:
    return [
        tx
        for tx in TRANSACTION_LOG
        if tx.operation_type == "CAPTURE" and tx.parent_operation_id == auth_operation_id
    ]


def _get_refunds_for_capture(capture_operation_id: str) -> List[TransactionLogEntry]:
    return [
        tx
        for tx in TRANSACTION_LOG
        if tx.operation_type == "REFUND" and tx.parent_operation_id == capture_operation_id
    ]


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
    logger.info("core-api startup complete")
    yield


app = FastAPI(
    title="NEFT Core API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Основной роутер v1
app.include_router(api_router, prefix="/api/v1")

# Включаем доп. роутер с чтением операций из БД, если он есть
if operations_router is not None:
    app.include_router(operations_router, prefix="")

# Включаем роутер транзакций, если он доступен
if transactions_router is not None:
    app.include_router(transactions_router, prefix="")

# Включаем роутер отчётов, если он доступен
if reports_billing_router is not None:
    app.include_router(reports_billing_router, prefix="")
if fuel_transactions_router is not None:
    app.include_router(fuel_transactions_router, prefix="")
if logistics_router is not None:
    app.include_router(logistics_router, prefix="")
if edo_events_router is not None:
    app.include_router(edo_events_router, prefix="")
if bi_router is not None:
    app.include_router(bi_router, prefix="")
if pricing_intelligence_router is not None:
    app.include_router(pricing_intelligence_router, prefix="")
if support_requests_router is not None:
    app.include_router(support_requests_router, prefix="")

if intake_router is not None:
    app.include_router(intake_router, prefix="")

if partners_router is not None:
    app.include_router(partners_router, prefix="")
if billing_invoices_router is not None:
    app.include_router(billing_invoices_router, prefix="")
if payouts_router is not None:
    app.include_router(payouts_router, prefix="")

app.include_router(admin_router, prefix=LEGACY_API_PREFIX)
app.include_router(admin_router, prefix=API_PREFIX_CORE)
app.include_router(kpi_router, prefix=API_PREFIX_CORE)
app.include_router(explain_v2_router, prefix=API_PREFIX_CORE)
app.include_router(cases_router, prefix=API_PREFIX_CORE)
app.include_router(achievements_router, prefix=API_PREFIX_CORE)
app.include_router(subscriptions_router, prefix=API_PREFIX_CORE)
app.include_router(subscriptions_admin_router, prefix=API_PREFIX_CORE)
app.include_router(client_router)
app.include_router(client_router, prefix=API_PREFIX_CORE)
app.include_router(fleet_router)
app.include_router(fleet_router, prefix=API_PREFIX_CORE)
app.include_router(client_portal_router, prefix=LEGACY_API_PREFIX)
app.include_router(client_portal_router, prefix=API_PREFIX_CORE)
app.include_router(portal_client_router, prefix=LEGACY_API_PREFIX)
app.include_router(portal_client_router, prefix=API_PREFIX_CORE)
app.include_router(portal_partner_router, prefix=LEGACY_API_PREFIX)
app.include_router(portal_partner_router, prefix=API_PREFIX_CORE)
app.include_router(client_documents_router)
app.include_router(internal_fleet_router)

# Префиксированный роутер для нового gateway namespace /api/core/*
core_prefixed_router = APIRouter(prefix="/api/core")
core_prefixed_router.include_router(api_router, prefix="/api/v1")

if operations_router is not None:
    core_prefixed_router.include_router(operations_router, prefix="")
if transactions_router is not None:
    core_prefixed_router.include_router(transactions_router, prefix="")
if reports_billing_router is not None:
    core_prefixed_router.include_router(reports_billing_router, prefix="")
if fuel_transactions_router is not None:
    core_prefixed_router.include_router(fuel_transactions_router, prefix="")
if logistics_router is not None:
    core_prefixed_router.include_router(logistics_router, prefix="")
if edo_events_router is not None:
    core_prefixed_router.include_router(edo_events_router, prefix="")
if bi_router is not None:
    core_prefixed_router.include_router(bi_router, prefix="")
if pricing_intelligence_router is not None:
    core_prefixed_router.include_router(pricing_intelligence_router, prefix="")
if support_requests_router is not None:
    core_prefixed_router.include_router(support_requests_router, prefix="")
if intake_router is not None:
    core_prefixed_router.include_router(intake_router, prefix="")
if partners_router is not None:
    core_prefixed_router.include_router(partners_router, prefix="")
if billing_invoices_router is not None:
    core_prefixed_router.include_router(billing_invoices_router, prefix="")
if payouts_router is not None:
    core_prefixed_router.include_router(payouts_router, prefix="")

core_prefixed_router.include_router(admin_router)
core_prefixed_router.include_router(kpi_router)
core_prefixed_router.include_router(explain_v2_router)
core_prefixed_router.include_router(cases_router)
core_prefixed_router.include_router(achievements_router)
core_prefixed_router.include_router(subscriptions_router)
core_prefixed_router.include_router(subscriptions_admin_router)
core_prefixed_router.include_router(client_router)
core_prefixed_router.include_router(fleet_router)
core_prefixed_router.include_router(client_portal_router)
core_prefixed_router.include_router(client_documents_router)
core_prefixed_router.include_router(internal_fleet_router)


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

    return [
        "# HELP core_api_cases_escalations_total Total SLA escalations by level.",
        "# TYPE core_api_cases_escalations_total counter",
        *escalation_lines,
        "# HELP core_api_cases_sla_breaches_total Total SLA breaches by kind.",
        "# TYPE core_api_cases_sla_breaches_total counter",
        *breach_lines,
    ]



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
    lines.extend(_accounting_export_metrics())
    lines.extend(_fleet_metrics())
    lines.extend(_bi_metrics())
    lines.extend(_reconciliation_metrics())
    return "\n".join(lines) + "\n"


@app.get("/metric", response_class=PlainTextResponse, include_in_schema=False)
def metric_alias() -> str:  # pragma: no cover - compatibility alias
    """Backward-compatible alias for the metrics endpoint."""

    return metrics()


# -----------------------------------------------------------------------------
# HEALTH
# -----------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse)
@app.get(f"{API_PREFIX_CORE}/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/health/db", response_model=HealthResponse)
def health_db(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        db.execute("SELECT 1")
        return HealthResponse(status="ok")
    except Exception as exc:  # pragma: no cover
        logger.exception("DB health failed: %s", exc)
        raise HTTPException(status_code=503, detail="db unavailable")


@app.get("/health/celery", response_model=HealthResponse)
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
    methods=["GET"],
)
core_prefixed_router.add_api_route(
    "/api/v1/health",
    health,
    response_model=HealthResponse,
    methods=["GET"],
)
core_prefixed_router.add_api_route(
    "/health/db",
    health_db,
    response_model=HealthResponse,
    methods=["GET"],
)
core_prefixed_router.add_api_route(
    "/health/celery",
    health_celery,
    response_model=HealthResponse,
    methods=["GET"],
)

app.include_router(core_prefixed_router)


@app.get("/api/core/openapi.json", include_in_schema=False)
def core_prefixed_openapi() -> dict[str, Any]:
    return app.openapi()


@app.get("/api/core/docs", include_in_schema=False)
def core_prefixed_docs():
    return get_swagger_ui_html(openapi_url="/api/core/openapi.json", title="NEFT Core API")


# -----------------------------------------------------------------------------
# Celery health
# -----------------------------------------------------------------------------
@app.get("/api/v1/health/enqueue", response_model=CeleryPingResponse)
def health_enqueue(
    wait: bool = Query(False, description="Wait synchronously for Celery ping result"),
) -> CeleryPingResponse:
    if not celery_app:
        # работаем в деградированном режиме без Celery
        return CeleryPingResponse(task="disabled", result={"pong": 1, "celery": "disabled"})

    try:
        async_result = celery_app.send_task("workers.ping", kwargs={"x": 1})
    except Exception as exc:
        logger.exception("Failed to enqueue Celery ping task: %s", exc)
        raise HTTPException(status_code=503, detail="Celery unavailable")

    if not wait:
        # просто проверяем, что задача успешно поставлена в очередь
        return CeleryPingResponse(
            task="ping",
            result={"queued": True, "task_id": async_result.id},
        )

    # Синхронное ожидание результата с обработкой таймаута
    try:
        result = async_result.get(timeout=5)
        return CeleryPingResponse(task="ping", result=result)
    except CeleryTimeoutError:
        logger.warning("Celery ping timeout, task_id=%s", async_result.id)
        # Не роняем /health/enqueue в 500, просто сигнализируем, что таймаут
        return CeleryPingResponse(
            task="ping",
            result={"error": "timeout", "task_id": async_result.id},
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("Celery ping failed: %s", exc)
        raise HTTPException(status_code=503, detail="Celery ping failed")


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


# -----------------------------------------------------------------------------
# AUTH
# -----------------------------------------------------------------------------
@app.post(
    "/api/v1/processing/terminal-auth",
    response_model=TransactionLogEntry,
)
def terminal_auth(body: TerminalAuthRequest = Body(...)) -> TransactionLogEntry:
    tx_type = body.tx_type or derive_tx_type(
        product_category=body.product_category, mcc=body.mcc
    )

    limits_result = call_limits_check_and_reserve_sync(
        CheckAndReserveRequest(
            merchant_id=body.merchant_id,
            terminal_id=body.terminal_id,
            client_id=body.client_id,
            card_id=body.card_id,
            amount=body.amount,
            currency=body.currency,
            product_category=body.product_category,
            mcc=body.mcc,
            tx_type=tx_type,
            phase="AUTH",
            client_group_id=body.client_group_id,
            card_group_id=body.card_group_id,
        )
    )

    op_id = str(uuid4())
    status = "AUTHORIZED" if limits_result.approved else "DECLINED"

    entry = TransactionLogEntry(
        operation_id=op_id,
        created_at=datetime.utcnow(),
        operation_type="AUTH",
        status=status,
        merchant_id=body.merchant_id,
        terminal_id=body.terminal_id,
        client_id=body.client_id,
        card_id=body.card_id,
        amount=body.amount,
        currency=body.currency,
        daily_limit=limits_result.daily_limit,
        limit_per_tx=limits_result.limit_per_tx,
        used_today=limits_result.used_today,
        new_used_today=limits_result.new_used_today,
        authorized=limits_result.approved,
        response_code=limits_result.response_code,
        response_message=limits_result.response_message,
        mcc=body.mcc,
        product_code=body.product_code,
        product_category=body.product_category,
        tx_type=tx_type,
    )
    _append_log_entry(entry)
    return entry


# -----------------------------------------------------------------------------
# CAPTURE
# -----------------------------------------------------------------------------
def _create_capture_entry(
    auth_tx: TransactionLogEntry,
    amount: int,
    limits_result: Optional[CheckAndReserveResult] = None,
) -> TransactionLogEntry:
    approved = limits_result.approved if limits_result else True
    status = "CAPTURED" if approved else "DECLINED"

    return TransactionLogEntry(
        operation_id=str(uuid4()),
        created_at=datetime.utcnow(),
        operation_type="CAPTURE",
        status=status,
        merchant_id=auth_tx.merchant_id,
        terminal_id=auth_tx.terminal_id,
        client_id=auth_tx.client_id,
        card_id=auth_tx.card_id,
        amount=amount,
        currency=auth_tx.currency,
        daily_limit=limits_result.daily_limit if limits_result else auth_tx.daily_limit,
        limit_per_tx=limits_result.limit_per_tx if limits_result else auth_tx.limit_per_tx,
        used_today=limits_result.used_today if limits_result else auth_tx.used_today,
        new_used_today=limits_result.new_used_today if limits_result else auth_tx.new_used_today,
        authorized=approved,
        response_code=limits_result.response_code if limits_result else "00",
        response_message=limits_result.response_message if limits_result else "captured",
        parent_operation_id=auth_tx.operation_id,
        mcc=auth_tx.mcc,
        product_code=auth_tx.product_code,
        product_category=auth_tx.product_category,
        tx_type=auth_tx.tx_type,
    )


@app.post(
    "/api/v1/transactions/{auth_operation_id}/capture",
    response_model=TransactionLogEntry,
)
def capture_transaction(
    auth_operation_id: str = Path(..., description="AUTH operation id"),
    body: CaptureRequest = Body(...),
) -> TransactionLogEntry:
    auth_tx = _get_transaction_or_404(auth_operation_id)
    if auth_tx.operation_type != "AUTH":
        raise HTTPException(status_code=400, detail="only AUTH can be captured")

    existing_captures = _get_captures_for_auth(auth_operation_id)
    already_captured_amount = sum(tx.amount for tx in existing_captures)
    if already_captured_amount + body.amount > auth_tx.amount:
        raise HTTPException(status_code=400, detail="capture amount exceeds authorized amount")

    capture_tx_type = auth_tx.tx_type or derive_tx_type(
        product_category=auth_tx.product_category, mcc=auth_tx.mcc
    )
    limits_result = call_limits_check_and_reserve_sync(
        CheckAndReserveRequest(
            merchant_id=auth_tx.merchant_id,
            terminal_id=auth_tx.terminal_id,
            client_id=auth_tx.client_id,
            card_id=auth_tx.card_id,
            amount=body.amount,
            currency=auth_tx.currency,
            product_category=auth_tx.product_category,
            mcc=auth_tx.mcc,
            tx_type=capture_tx_type,
            phase="CAPTURE",
        )
    )

    entry = _create_capture_entry(auth_tx, body.amount, limits_result)
    _append_log_entry(entry)
    return entry


# -----------------------------------------------------------------------------
# REFUND
# -----------------------------------------------------------------------------
def _create_refund_entry(
    capture_tx: TransactionLogEntry,
    amount: int,
    reason: Optional[str],
) -> TransactionLogEntry:
    return TransactionLogEntry(
        operation_id=str(uuid4()),
        created_at=datetime.utcnow(),
        operation_type="REFUND",
        status="REFUNDED",
        merchant_id=capture_tx.merchant_id,
        terminal_id=capture_tx.terminal_id,
        client_id=capture_tx.client_id,
        card_id=capture_tx.card_id,
        amount=amount,
        currency=capture_tx.currency,
        daily_limit=capture_tx.daily_limit,
        limit_per_tx=capture_tx.limit_per_tx,
        used_today=capture_tx.used_today,
        new_used_today=capture_tx.new_used_today,
        authorized=True,
        response_code="00",
        response_message="refunded",
        parent_operation_id=capture_tx.operation_id,
        reason=reason,
        mcc=capture_tx.mcc,
        product_code=capture_tx.product_code,
        product_category=capture_tx.product_category,
        tx_type=capture_tx.tx_type,
    )


@app.post(
    "/api/v1/transactions/{capture_operation_id}/refund",
    response_model=TransactionLogEntry,
)
def refund_transaction(
    capture_operation_id: str = Path(..., description="CAPTURE operation id"),
    body: RefundRequest = Body(...),
) -> TransactionLogEntry:
    capture_tx = _get_transaction_or_404(capture_operation_id)
    if capture_tx.operation_type != "CAPTURE":
        raise HTTPException(status_code=400, detail="only CAPTURE can be refunded")

    refunds = _get_refunds_for_capture(capture_operation_id)
    already_refunded = sum(tx.amount for tx in refunds)

    # Сколько ещё можно вернуть
    remaining = capture_tx.amount - already_refunded
    if remaining <= 0:
        raise HTTPException(status_code=400, detail="nothing to refund")

    # Если amount не передан → FULL REFUND на оставшуюся сумму
    if body.amount is None:
        refund_amount = remaining
    else:
        refund_amount = body.amount

    if refund_amount <= 0:
        raise HTTPException(status_code=400, detail="refund amount must be positive")

    if already_refunded + refund_amount > capture_tx.amount:
        raise HTTPException(status_code=400, detail="refund amount exceeds captured amount")

    entry = _create_refund_entry(capture_tx, refund_amount, body.reason)
    _append_log_entry(entry)
    return entry


# -----------------------------------------------------------------------------
# REVERSAL
# -----------------------------------------------------------------------------
def _create_reversal_entry(
    original_tx: TransactionLogEntry,
    reason: Optional[str],
) -> TransactionLogEntry:
    return TransactionLogEntry(
        operation_id=str(uuid4()),
        created_at=datetime.utcnow(),
        operation_type="REVERSAL",
        status="REVERSED",
        merchant_id=original_tx.merchant_id,
        terminal_id=original_tx.terminal_id,
        client_id=original_tx.client_id,
        card_id=original_tx.card_id,
        amount=original_tx.amount,
        currency=original_tx.currency,
        daily_limit=original_tx.daily_limit,
        limit_per_tx=original_tx.limit_per_tx,
        used_today=original_tx.used_today,
        new_used_today=original_tx.new_used_today,
        authorized=False,
        response_code="00",
        response_message="reversed",
        parent_operation_id=original_tx.operation_id,
        reason=reason,
        mcc=original_tx.mcc,
        product_code=original_tx.product_code,
        product_category=original_tx.product_category,
        tx_type=original_tx.tx_type,
    )


@app.post(
    "/api/v1/transactions/{operation_id}/reversal",
    response_model=TransactionLogEntry,
)
def reverse_transaction(
    operation_id: str = Path(..., description="operation id to reverse"),
    body: ReversalRequest = Body(...),
) -> TransactionLogEntry:
    original_tx = _get_transaction_or_404(operation_id)

    # нельзя ревёрсить уже ревёрснутые операции
    if original_tx.operation_type == "REVERSAL":
        raise HTTPException(status_code=400, detail="cannot reverse reversal")

    # проверим, не был ли уже сделан REVERSAL для этой операции
    children = _get_children(original_tx.operation_id)
    if any(child.operation_type == "REVERSAL" for child in children):
        raise HTTPException(status_code=400, detail="reversal already exists for this operation")

    entry = _create_reversal_entry(original_tx, body.reason)
    _append_log_entry(entry)
    return entry


# -----------------------------------------------------------------------------
# ЧТЕНИЕ in-memory лога
# -----------------------------------------------------------------------------
@app.get("/api/v1/transactions/log", response_model=TransactionsPage)
def list_operations_log(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> TransactionsPage:
    # Возвращаем в обратном порядке (сначала последние)
    items = list(reversed(TRANSACTION_LOG))
    total = len(items)
    slice_ = items[offset : offset + limit]
    return TransactionsPage(
        items=slice_,
        total=total,
        limit=limit,
        offset=offset,
    )
