from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import requests
from redis import Redis
from sqlalchemy import func, inspect
from sqlalchemy.orm import Session

from app.config import settings
from app.models.audit_log import AuditLog
from app.models.partner_finance import PartnerLedgerEntry, PartnerLedgerEntryType
from app.models.payout_order import PayoutOrder, PayoutOrderStatus
from app.models.settlement_v1 import SettlementPeriod, SettlementPeriodStatus
from app.models.support_ticket import SupportTicket, SupportTicketSlaStatus
from app.schemas.admin.runtime_summary import (
    ExternalProviderHealth,
    ExternalProviderStatus,
    HealthStatus,
    RuntimeEvent,
    RuntimeEvents,
    RuntimeHealth,
    RuntimeMoneyRisk,
    RuntimeQueueCount,
    RuntimeQueues,
    RuntimeQueueState,
    RuntimeSummaryResponse,
    RuntimeViolationTop,
    RuntimeViolations,
)
from app.services.geo_clickhouse import clickhouse_ping
from app.services.mor_metrics import metrics as mor_metrics


CRITICAL_EVENT_TYPES = {
    "FINANCIAL_INVARIANT_VIOLATION",
    "OPS_ESCALATION_CREATED",
    "PAYOUT_APPROVED",
    "PAYOUT_MARKED_PAID",
    "PAYOUT_REJECTED",
}
PROBE_TIMEOUT_SECONDS = 1.0

HEALTH_PROBE_URLS = {
    "auth_host": "http://auth-host:8000/api/auth/health",
    "gateway": "http://gateway/health",
    "integration_hub": "http://integration-hub:8000/health",
    "document_service": "http://document-service:8000/health",
    "logistics_service": "http://logistics-service:8000/health",
    "ai_service": "http://ai-service:8000/api/v1/health",
    "minio": "http://minio:9000/minio/health/ready",
    "prometheus": "http://prometheus:9090/-/healthy",
    "grafana": "http://grafana:3000/api/health",
    "loki": "http://loki:3100/ready",
    "otel_collector": "http://otel-collector:13133/",
}

METRICS_PROBE_URLS = {
    "gateway": "http://gateway/metrics",
    "core_api": "http://127.0.0.1:8000/metrics",
    "auth_host": "http://auth-host:8000/api/v1/metrics",
    "integration_hub": "http://integration-hub:8000/metrics",
    "document_service": "http://document-service:8000/metrics",
    "logistics_service": "http://logistics-service:8000/metrics",
    "ai_service": "http://ai-service:8000/metrics",
}


def _normalize_env_name(raw: str) -> str:
    value = raw.lower()
    if value in {"local", "dev"}:
        return "dev"
    if "stage" in value:
        return "stage"
    if "prod" in value:
        return "prod"
    return value


def _count(query) -> int:
    value = query.scalar()
    return int(value or 0)


def _table_available(db: Session, model) -> bool:
    table = model.__table__
    connection = db.connection()
    inspector = inspect(connection)
    schema = getattr(table, "schema", None)
    if schema:
        return inspector.has_table(table.name, schema=schema)
    return inspector.has_table(table.name)


def _track_table(db: Session, model, missing_tables: set[str]) -> bool:
    available = _table_available(db, model)
    if not available:
        missing_tables.add(model.__table__.name)
    return available


def _queue_state(db: Session, *, model, status_field, status_value) -> RuntimeQueueState:
    oldest = (
        db.query(model)
        .filter(status_field == status_value)
        .order_by(model.created_at.asc())
        .first()
    )
    now = datetime.now(timezone.utc)
    oldest_age_sec = 0
    if oldest and getattr(oldest, "created_at", None):
        oldest_age_sec = int((now - oldest.created_at).total_seconds())
    depth = _count(db.query(func.count(model.id)).filter(status_field == status_value))
    return RuntimeQueueState(depth=depth, oldest_age_sec=oldest_age_sec)


def _http_probe_status(url: str) -> HealthStatus:
    try:
        response = requests.get(url, timeout=PROBE_TIMEOUT_SECONDS)
        return HealthStatus.UP if response.status_code < 400 else HealthStatus.DOWN
    except Exception:  # noqa: BLE001
        return HealthStatus.DOWN


def _http_probe_json(url: str) -> dict | None:
    try:
        response = requests.get(url, timeout=PROBE_TIMEOUT_SECONDS)
        if response.headers.get("content-type", "").startswith("application/json") or response.text.strip().startswith("{"):
            return response.json()
    except Exception:  # noqa: BLE001
        return None
    return None


def _redis_probe_status() -> HealthStatus:
    try:
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        return HealthStatus.UP if bool(client.ping()) else HealthStatus.DOWN
    except Exception:  # noqa: BLE001
        return HealthStatus.DOWN


def _clickhouse_probe_status() -> HealthStatus:
    return HealthStatus.UP if clickhouse_ping() else HealthStatus.DOWN


def _status_warning(prefix: str, service: str, status: HealthStatus) -> str | None:
    if status == HealthStatus.UP:
        return None
    return f"{prefix}_{status.value.lower()}:{service}"


def _build_observed_health() -> tuple[dict[str, HealthStatus], list[str]]:
    observed = {
        "core_api": HealthStatus.UP,
        "auth_host": _http_probe_status(HEALTH_PROBE_URLS["auth_host"]),
        "gateway": _http_probe_status(HEALTH_PROBE_URLS["gateway"]),
        "integration_hub": _http_probe_status(HEALTH_PROBE_URLS["integration_hub"]),
        "document_service": _http_probe_status(HEALTH_PROBE_URLS["document_service"]),
        "logistics_service": _http_probe_status(HEALTH_PROBE_URLS["logistics_service"]),
        "ai_service": _http_probe_status(HEALTH_PROBE_URLS["ai_service"]),
        "redis": _redis_probe_status(),
        "minio": _http_probe_status(HEALTH_PROBE_URLS["minio"]),
        "clickhouse": _clickhouse_probe_status(),
        "prometheus": _http_probe_status(HEALTH_PROBE_URLS["prometheus"]),
        "grafana": _http_probe_status(HEALTH_PROBE_URLS["grafana"]),
        "loki": _http_probe_status(HEALTH_PROBE_URLS["loki"]),
        "otel_collector": _http_probe_status(HEALTH_PROBE_URLS["otel_collector"]),
    }
    warnings: list[str] = []
    for service, status in observed.items():
        warning = _status_warning("health", service, status)
        if warning:
            warnings.append(warning)
    for service, url in METRICS_PROBE_URLS.items():
        warning = _status_warning("metrics", service, _http_probe_status(url))
        if warning:
            warnings.append(warning)
    return observed, warnings


def _provider_status(raw: object) -> ExternalProviderStatus:
    try:
        return ExternalProviderStatus(str(raw or "").strip().upper())
    except ValueError:
        return ExternalProviderStatus.DEGRADED


def _provider_from_payload(item: dict, *, service: str) -> ExternalProviderHealth:
    return ExternalProviderHealth(
        service=str(item.get("service") or service),
        provider=str(item.get("provider") or "unknown_provider"),
        mode=str(item.get("mode") or "unknown"),
        status=_provider_status(item.get("status")),
        configured=bool(item.get("configured", False)),
        last_success_at=item.get("last_success_at"),
        last_error_code=item.get("last_error_code"),
        message=item.get("message"),
    )


def _provider_mode_status(mode: str, *, configured: bool = False, unsupported_by_default: bool = False) -> ExternalProviderStatus:
    normalized = (mode or "").strip().lower()
    if normalized in {"", "disabled"}:
        return ExternalProviderStatus.DISABLED
    if normalized == "degraded":
        return ExternalProviderStatus.DEGRADED
    if normalized in {"mock", "stub"}:
        return ExternalProviderStatus.CONFIGURED
    if unsupported_by_default:
        return ExternalProviderStatus.UNSUPPORTED
    return ExternalProviderStatus.HEALTHY if configured else ExternalProviderStatus.DEGRADED


def _local_provider_health() -> list[ExternalProviderHealth]:
    bank_mode = os.getenv("BANK_PROVIDER_MODE", os.getenv("BANK_API_PROVIDER_MODE", "unsupported")).strip().lower()
    erp_mode = os.getenv("ERP_DELIVERY_MODE", "file_only").strip().lower()
    fuel_mode = os.getenv("FUEL_PROVIDER_MODE", "unsupported").strip().lower()
    bank_configured = bool(os.getenv("BANK_API_BASE_URL", "").strip())
    erp_configured = erp_mode == "file_only" or bool(os.getenv("ERP_1C_BASE_URL", "").strip())
    fuel_configured = bool(os.getenv("FUEL_PROVIDER_BASE_URL", "").strip())
    return [
        ExternalProviderHealth(
            service="processing-core",
            provider="bank_api_statements",
            mode=bank_mode or "unsupported",
            status=_provider_mode_status(bank_mode, configured=bank_configured, unsupported_by_default=bank_mode == "unsupported"),
            configured=bank_configured,
            last_error_code=None if bank_configured else "bank_vendor_not_selected",
            message="Statement file/import path remains canonical; live bank API is gated by selected vendor credentials",
        ),
        ExternalProviderHealth(
            service="processing-core",
            provider="erp_1c_delivery",
            mode=erp_mode or "file_only",
            status=ExternalProviderStatus.CONFIGURED if erp_mode == "file_only" else _provider_mode_status(erp_mode, configured=erp_configured),
            configured=erp_configured,
            last_error_code=None if erp_configured else "erp_transport_not_configured",
            message="1C export payload generation is available; API delivery requires concrete 1C endpoint/protocol",
        ),
        ExternalProviderHealth(
            service="processing-core",
            provider="fuel_provider",
            mode=fuel_mode or "unsupported",
            status=_provider_mode_status(fuel_mode, configured=fuel_configured, unsupported_by_default=fuel_mode == "unsupported"),
            configured=fuel_configured,
            last_error_code=None if fuel_configured else "fuel_vendor_not_selected",
            message="Fuel provider write/ingest owner stays blocked until a concrete vendor is selected",
        ),
    ]


def _build_external_provider_health() -> tuple[list[ExternalProviderHealth], list[str]]:
    providers: list[ExternalProviderHealth] = []
    for service, url in {
        "integration-hub": HEALTH_PROBE_URLS["integration_hub"],
        "document-service": HEALTH_PROBE_URLS["document_service"],
        "logistics-service": HEALTH_PROBE_URLS["logistics_service"],
    }.items():
        payload = _http_probe_json(url)
        for item in (payload or {}).get("external_providers", []):
            if isinstance(item, dict):
                providers.append(_provider_from_payload(item, service=service))
    providers.extend(_local_provider_health())
    warning_statuses = {
        ExternalProviderStatus.DEGRADED,
        ExternalProviderStatus.AUTH_FAILED,
        ExternalProviderStatus.TIMEOUT,
        ExternalProviderStatus.UNSUPPORTED,
        ExternalProviderStatus.RATE_LIMITED,
    }
    warnings = [
        f"provider_{provider.status.value.lower()}:{provider.service}:{provider.provider}"
        for provider in providers
        if provider.status in warning_statuses
    ]
    return providers, warnings


def build_runtime_summary(db: Session) -> RuntimeSummaryResponse:
    environment = _normalize_env_name(os.getenv("NEFT_ENV", "dev"))
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    missing_tables: set[str] = set()

    payout_table_ready = _track_table(db, PayoutOrder, missing_tables)
    settlement_table_ready = _track_table(db, SettlementPeriod, missing_tables)
    audit_table_ready = _track_table(db, AuditLog, missing_tables)
    partner_ledger_ready = _track_table(db, PartnerLedgerEntry, missing_tables)
    support_ticket_ready = _track_table(db, SupportTicket, missing_tables)

    payouts_queue = (
        _queue_state(
            db,
            model=PayoutOrder,
            status_field=PayoutOrder.status,
            status_value=PayoutOrderStatus.QUEUED,
        )
        if payout_table_ready
        else RuntimeQueueState(depth=0, oldest_age_sec=0)
    )
    settlement_queue = (
        _queue_state(
            db,
            model=SettlementPeriod,
            status_field=SettlementPeriod.status,
            status_value=SettlementPeriodStatus.OPEN,
        )
        if settlement_table_ready
        else RuntimeQueueState(depth=0, oldest_age_sec=0)
    )
    blocked_payouts = (
        _count(db.query(func.count(PayoutOrder.id)).filter(PayoutOrder.status == PayoutOrderStatus.FAILED))
        if payout_table_ready
        else 0
    )

    immutable_violations = mor_metrics.settlement_immutable_violation_total
    invariant_logs = (
        db.query(AuditLog)
        .filter(
            AuditLog.event_type == "FINANCIAL_INVARIANT_VIOLATION",
            AuditLog.ts >= since_24h,
        )
        .order_by(AuditLog.ts.desc())
        .limit(200)
        .all()
        if audit_table_ready
        else []
    )
    invariant_reason_counts: dict[str, int] = {}
    for item in invariant_logs:
        reason = item.reason or "UNKNOWN"
        invariant_reason_counts[reason] = invariant_reason_counts.get(reason, 0) + 1
    invariant_top = [reason for reason, _ in sorted(invariant_reason_counts.items(), key=lambda r: r[1], reverse=True)[:5]]
    invariant_count = sum(invariant_reason_counts.values())

    sla_penalties = (
        _count(
            db.query(func.count(PartnerLedgerEntry.id)).filter(
                PartnerLedgerEntry.entry_type == PartnerLedgerEntryType.SLA_PENALTY,
                PartnerLedgerEntry.created_at >= since_24h,
            )
        )
        if partner_ledger_ready
        else 0
    )
    sla_breaches = (
        _count(
            db.query(func.count(SupportTicket.id)).filter(
                (SupportTicket.sla_first_response_status == SupportTicketSlaStatus.BREACHED)
                | (SupportTicket.sla_resolution_status == SupportTicketSlaStatus.BREACHED),
                SupportTicket.updated_at >= since_24h,
            )
        )
        if support_ticket_ready
        else 0
    )
    critical_logs = (
        db.query(AuditLog)
        .filter(AuditLog.event_type.in_(CRITICAL_EVENT_TYPES))
        .order_by(AuditLog.ts.desc())
        .limit(10)
        .all()
        if audit_table_ready
        else []
    )
    critical_events = [
        RuntimeEvent(
            ts=item.ts.isoformat(),
            kind=item.event_type,
            message=item.reason or item.action,
            correlation_id=item.trace_id or item.request_id,
        )
        for item in critical_logs
    ]
    observed_health, probe_warnings = _build_observed_health()
    external_provider_health, provider_warnings = _build_external_provider_health()
    postgres_health = HealthStatus.DEGRADED if missing_tables else HealthStatus.UP
    missing_table_names = sorted(missing_tables)
    health_snapshot = RuntimeHealth(
        **observed_health,
        postgres=postgres_health,
    )
    warnings = [
        *probe_warnings,
        *provider_warnings,
        *[f"missing_table:{table_name}" for table_name in missing_table_names],
    ]
    return RuntimeSummaryResponse(
        ts=now,
        environment=environment,
        read_only=settings.ADMIN_READ_ONLY,
        health=health_snapshot,
        queues=RuntimeQueues(
            settlement=settlement_queue,
            payout=payouts_queue,
            blocked_payouts=RuntimeQueueCount(count=blocked_payouts),
            payment_intakes_pending=RuntimeQueueCount(count=0),
        ),
        violations=RuntimeViolations(
            immutable=RuntimeViolationTop(count=immutable_violations, top=[]),
            invariants=RuntimeViolationTop(count=invariant_count, top=invariant_top),
            sla_penalties=RuntimeViolationTop(count=sla_penalties, top=[]),
        ),
        money_risk=RuntimeMoneyRisk(
            payouts_blocked=blocked_payouts,
            settlements_pending=settlement_queue.depth,
            overdue_clients=sla_breaches,
        ),
        events=RuntimeEvents(critical_last_10=critical_events),
        warnings=warnings,
        missing_tables=missing_table_names,
        external_providers=external_provider_health,
    )


__all__ = ["build_runtime_summary"]
