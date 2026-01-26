from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.audit_log import AuditLog
from app.models.partner_finance import PartnerLedgerEntry, PartnerLedgerEntryType
from app.models.payout_order import PayoutOrder, PayoutOrderStatus
from app.models.settlement_v1 import SettlementPeriod, SettlementPeriodStatus
from app.models.support_ticket import SupportTicket, SupportTicketSlaStatus
from app.schemas.admin.runtime_summary import (
    HealthStatus,
    RuntimeEvents,
    RuntimeHealth,
    RuntimeMoneyRisk,
    RuntimeQueues,
    RuntimeQueueCount,
    RuntimeQueueState,
    RuntimeEvent,
    RuntimeSummaryResponse,
    RuntimeViolations,
    RuntimeViolationTop,
)
from app.services.mor_metrics import metrics as mor_metrics


CRITICAL_EVENT_TYPES = {
    "FINANCIAL_INVARIANT_VIOLATION",
    "OPS_ESCALATION_CREATED",
    "PAYOUT_APPROVED",
    "PAYOUT_MARKED_PAID",
    "PAYOUT_REJECTED",
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


def build_runtime_summary(db: Session) -> RuntimeSummaryResponse:
    environment = _normalize_env_name(os.getenv("NEFT_ENV", "dev"))
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)

    payouts_queue = _queue_state(
        db,
        model=PayoutOrder,
        status_field=PayoutOrder.status,
        status_value=PayoutOrderStatus.QUEUED,
    )
    settlement_queue = _queue_state(
        db,
        model=SettlementPeriod,
        status_field=SettlementPeriod.status,
        status_value=SettlementPeriodStatus.OPEN,
    )
    blocked_payouts = _count(
        db.query(func.count(PayoutOrder.id)).filter(PayoutOrder.status == PayoutOrderStatus.FAILED)
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
    )
    invariant_reason_counts: dict[str, int] = {}
    for item in invariant_logs:
        reason = item.reason or "UNKNOWN"
        invariant_reason_counts[reason] = invariant_reason_counts.get(reason, 0) + 1
    invariant_top = [reason for reason, _ in sorted(invariant_reason_counts.items(), key=lambda r: r[1], reverse=True)[:5]]
    invariant_count = sum(invariant_reason_counts.values())

    sla_penalties = _count(
        db.query(func.count(PartnerLedgerEntry.id)).filter(
            PartnerLedgerEntry.entry_type == PartnerLedgerEntryType.SLA_PENALTY,
            PartnerLedgerEntry.created_at >= since_24h,
        )
    )
    sla_breaches = _count(
        db.query(func.count(SupportTicket.id)).filter(
            (SupportTicket.sla_first_response_status == SupportTicketSlaStatus.BREACHED)
            | (SupportTicket.sla_resolution_status == SupportTicketSlaStatus.BREACHED),
            SupportTicket.updated_at >= since_24h,
        )
    )
    critical_logs = (
        db.query(AuditLog)
        .filter(AuditLog.event_type.in_(CRITICAL_EVENT_TYPES))
        .order_by(AuditLog.ts.desc())
        .limit(10)
        .all()
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
    return RuntimeSummaryResponse(
        ts=now,
        environment=environment,
        read_only=settings.ADMIN_READ_ONLY,
        health=RuntimeHealth(
            core_api=HealthStatus.UP,
            auth_host=HealthStatus.UP,
            gateway=HealthStatus.UP,
            postgres=HealthStatus.UP,
            redis=HealthStatus.UP,
            minio=HealthStatus.UP,
            clickhouse=HealthStatus.UP,
        ),
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
    )


__all__ = ["build_runtime_summary"]
