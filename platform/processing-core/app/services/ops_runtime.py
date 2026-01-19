from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.bank_statement_imports import (
    BankStatementImport,
    BankStatementImportStatus,
    BankStatementMatchStatus,
    BankStatementTransaction,
)
from app.models.billing_dunning import BillingDunningEvent, BillingDunningEventType, BillingDunningStatus
from app.models.email_outbox import EmailOutbox, EmailOutboxStatus
from app.models.export_jobs import ExportJob, ExportJobStatus
from app.models.helpdesk import HelpdeskOutbox, HelpdeskOutboxStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payout_order import PayoutOrder, PayoutOrderStatus
from app.models.settlement_v1 import SettlementPeriod, SettlementPeriodStatus
from app.models.support_ticket import SupportTicket, SupportTicketSlaStatus, SupportTicketStatus
from app.schemas.admin.ops_runtime import (
    OpsBillingSummary,
    OpsCoreSummary,
    OpsEnvSummary,
    OpsExportsSummary,
    OpsFailedReconciliationImport,
    OpsFailedExportItem,
    OpsHealthResponse,
    OpsHelpdeskQueueSummary,
    OpsMorSummary,
    OpsMorTopReason,
    OpsBlockedPayoutItem,
    OpsPayoutQueueSummary,
    OpsQueuesSummary,
    OpsReconciliationSummary,
    OpsSettlementQueueSummary,
    OpsSignalsSummary,
    OpsSummaryResponse,
    OpsSupportBreachItem,
    OpsSupportSummary,
    OpsTimeSummary,
)
from app.services.mor_metrics import metrics as mor_metrics

OVERDUE_ORGS_YELLOW_THRESHOLD = 5
EXPORTS_FAILED_1H_YELLOW_THRESHOLD = 3
PAYOUT_QUEUE_RED_THRESHOLD = 100
PAYOUT_BLOCKED_RED_THRESHOLD = 1


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _count(query) -> int:
    value = query.scalar()
    return int(value or 0)


def _sum(query) -> int:
    value = query.scalar()
    return int(value or 0)


def _avg_seconds(query) -> int:
    value = query.scalar()
    if value is None:
        return 0
    return int(value)


def _build_signals(
    *,
    immutable_violations: int,
    clawback_required: int,
    payout_blocked: int,
    payouts_queued: int,
    overdue_orgs: int,
    exports_failed_1h: int,
    reconciliation_parse_failed: int,
) -> OpsSignalsSummary:
    status = "GREEN"
    reasons: list[str] = []

    def mark_red(reason: str) -> None:
        nonlocal status
        status = "RED"
        reasons.append(reason)

    def mark_yellow(reason: str) -> None:
        nonlocal status
        if status != "RED":
            status = "YELLOW"
        reasons.append(reason)

    if immutable_violations > 0:
        mark_red("MoR immutable violations in last 24h")
    if clawback_required > 0:
        mark_red("Clawback required in last 24h")
    if payout_blocked >= PAYOUT_BLOCKED_RED_THRESHOLD:
        mark_red("Payouts blocked spike detected")
    if payouts_queued >= PAYOUT_QUEUE_RED_THRESHOLD:
        mark_red("Payout queue backlog exceeds threshold")

    if overdue_orgs >= OVERDUE_ORGS_YELLOW_THRESHOLD:
        mark_yellow("Overdue orgs above threshold")
    if exports_failed_1h >= EXPORTS_FAILED_1H_YELLOW_THRESHOLD:
        mark_yellow("Exports failed in last hour above threshold")
    if reconciliation_parse_failed > 0:
        mark_yellow("Reconciliation parse failures in last 24h")

    return OpsSignalsSummary(status=status, reasons=reasons)


def build_ops_summary(db: Session) -> OpsSummaryResponse:
    now = _utc_now()
    since_1h = now - timedelta(hours=1)
    since_24h = now - timedelta(hours=24)

    export_queued = _count(
        db.query(func.count(ExportJob.id)).filter(ExportJob.status == ExportJobStatus.QUEUED)
    )
    export_running = _count(
        db.query(func.count(ExportJob.id)).filter(ExportJob.status == ExportJobStatus.RUNNING)
    )
    export_failed_1h = _count(
        db.query(func.count(ExportJob.id)).filter(
            ExportJob.status == ExportJobStatus.FAILED,
            ExportJob.created_at >= since_1h,
        )
    )

    payouts_queued = _count(
        db.query(func.count(PayoutOrder.id)).filter(PayoutOrder.status == PayoutOrderStatus.QUEUED)
    )
    payout_blocked_total = sum(mor_metrics.payout_blocked_total.values())

    settlements_queued = _count(
        db.query(func.count(SettlementPeriod.id)).filter(
            SettlementPeriod.status == SettlementPeriodStatus.OPEN
        )
    )
    settlements_finalizing = _count(
        db.query(func.count(SettlementPeriod.id)).filter(
            SettlementPeriod.status.in_({SettlementPeriodStatus.CALCULATED, SettlementPeriodStatus.APPROVED})
        )
    )

    emails_queued = _count(
        db.query(func.count(EmailOutbox.id)).filter(EmailOutbox.status == EmailOutboxStatus.QUEUED)
    )
    emails_failed_1h = _count(
        db.query(func.count(EmailOutbox.id)).filter(
            EmailOutbox.status == EmailOutboxStatus.FAILED,
            EmailOutbox.created_at >= since_1h,
        )
    )

    helpdesk_queued = _count(
        db.query(func.count(HelpdeskOutbox.id)).filter(HelpdeskOutbox.status == HelpdeskOutboxStatus.QUEUED)
    )
    helpdesk_failed_1h = _count(
        db.query(func.count(HelpdeskOutbox.id)).filter(
            HelpdeskOutbox.status == HelpdeskOutboxStatus.FAILED,
            HelpdeskOutbox.created_at >= since_1h,
        )
    )

    immutable_violations = mor_metrics.settlement_immutable_violation_total
    clawback_required = mor_metrics.clawback_required_total
    admin_overrides = mor_metrics.admin_override_total
    payout_blocked_reasons = [
        OpsMorTopReason(reason=reason, count=count)
        for reason, count in sorted(
            mor_metrics.payout_blocked_total.items(), key=lambda item: item[1], reverse=True
        )[:5]
    ]

    overdue_orgs = _count(
        db.query(func.count(func.distinct(Invoice.client_id))).filter(Invoice.status == InvoiceStatus.OVERDUE)
    )
    overdue_amount = _sum(
        db.query(func.coalesce(func.sum(Invoice.amount_due), 0)).filter(Invoice.status == InvoiceStatus.OVERDUE)
    )
    dunning_sent_24h = _count(
        db.query(func.count(BillingDunningEvent.id)).filter(
            BillingDunningEvent.status == BillingDunningStatus.SENT,
            BillingDunningEvent.sent_at >= since_24h,
        )
    )
    auto_suspends_24h = _count(
        db.query(func.count(BillingDunningEvent.id)).filter(
            BillingDunningEvent.event_type == BillingDunningEventType.SUSPENDED,
            BillingDunningEvent.sent_at >= since_24h,
        )
    )

    imports_24h = _count(
        db.query(func.count(BankStatementImport.id)).filter(BankStatementImport.uploaded_at >= since_24h)
    )
    parse_failed_24h = _count(
        db.query(func.count(BankStatementImport.id)).filter(
            BankStatementImport.status == BankStatementImportStatus.FAILED,
            BankStatementImport.uploaded_at >= since_24h,
        )
    )
    unmatched_24h = _count(
        db.query(func.count(BankStatementTransaction.id)).filter(
            BankStatementTransaction.matched_status == BankStatementMatchStatus.UNMATCHED,
            BankStatementTransaction.created_at >= since_24h,
        )
    )
    auto_approved_24h = _count(
        db.query(func.count(BankStatementTransaction.id)).filter(
            BankStatementTransaction.matched_status == BankStatementMatchStatus.MATCHED,
            BankStatementTransaction.created_at >= since_24h,
        )
    )

    export_jobs_24h = _count(
        db.query(func.count(ExportJob.id)).filter(ExportJob.created_at >= since_24h)
    )
    export_failed_24h = _count(
        db.query(func.count(ExportJob.id)).filter(
            ExportJob.status == ExportJobStatus.FAILED,
            ExportJob.created_at >= since_24h,
        )
    )
    export_avg_duration = _avg_seconds(
        db.query(func.avg(func.extract("epoch", ExportJob.finished_at - ExportJob.started_at))).filter(
            ExportJob.finished_at.isnot(None),
            ExportJob.started_at.isnot(None),
            ExportJob.finished_at >= since_24h,
        )
    )

    open_tickets = _count(
        db.query(func.count(SupportTicket.id)).filter(
            SupportTicket.status.in_({SupportTicketStatus.OPEN, SupportTicketStatus.IN_PROGRESS})
        )
    )
    sla_breaches_24h = _count(
        db.query(func.count(SupportTicket.id)).filter(
            or_(
                SupportTicket.sla_first_response_status == SupportTicketSlaStatus.BREACHED,
                SupportTicket.sla_resolution_status == SupportTicketSlaStatus.BREACHED,
            ),
            SupportTicket.updated_at >= since_24h,
        )
    )

    signals = _build_signals(
        immutable_violations=immutable_violations,
        clawback_required=clawback_required,
        payout_blocked=payout_blocked_total,
        payouts_queued=payouts_queued,
        overdue_orgs=overdue_orgs,
        exports_failed_1h=export_failed_1h,
        reconciliation_parse_failed=parse_failed_24h,
    )

    return OpsSummaryResponse(
        env=OpsEnvSummary.from_env(),
        time=OpsTimeSummary(now=now),
        core=OpsCoreSummary(health="ok"),
        queues=OpsQueuesSummary(
            exports=OpsQueuesSummary.build_exports(queued=export_queued, running=export_running, failed_1h=export_failed_1h),
            payouts=OpsPayoutQueueSummary(queued=payouts_queued, blocked=payout_blocked_total),
            settlements=OpsSettlementQueueSummary(queued=settlements_queued, finalizing=settlements_finalizing),
            emails=OpsQueuesSummary.build_emails(queued=emails_queued, failed_1h=emails_failed_1h),
            helpdesk_outbox=OpsHelpdeskQueueSummary(queued=helpdesk_queued, failed_1h=helpdesk_failed_1h),
        ),
        mor=OpsMorSummary(
            immutable_violations_24h=immutable_violations,
            payout_blocked_total_24h=payout_blocked_total,
            payout_blocked_top_reasons=payout_blocked_reasons,
            clawback_required_24h=clawback_required,
            admin_overrides_24h=admin_overrides,
        ),
        billing=OpsBillingSummary(
            overdue_orgs=overdue_orgs,
            overdue_amount=overdue_amount,
            dunning_sent_24h=dunning_sent_24h,
            auto_suspends_24h=auto_suspends_24h,
        ),
        reconciliation=OpsReconciliationSummary(
            imports_24h=imports_24h,
            parse_failed_24h=parse_failed_24h,
            unmatched_24h=unmatched_24h,
            auto_approved_24h=auto_approved_24h,
        ),
        exports=OpsExportsSummary(
            jobs_24h=export_jobs_24h,
            failed_24h=export_failed_24h,
            avg_duration_sec=export_avg_duration,
        ),
        support=OpsSupportSummary(open_tickets=open_tickets, sla_breaches_24h=sla_breaches_24h),
        signals=signals,
    )


def build_ops_health() -> OpsHealthResponse:
    return OpsHealthResponse(ok=True)


def list_blocked_payouts(db: Session, *, limit: int) -> list[OpsBlockedPayoutItem]:
    rows = (
        db.query(PayoutOrder)
        .filter(PayoutOrder.status == PayoutOrderStatus.FAILED)
        .order_by(PayoutOrder.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        OpsBlockedPayoutItem(
            id=item.id,
            settlement_id=item.settlement_id,
            status=item.status,
            amount=item.amount,
            currency=item.currency,
            created_at=item.created_at,
            error=item.error,
        )
        for item in rows
    ]


def list_failed_exports(db: Session, *, limit: int) -> list[OpsFailedExportItem]:
    rows = (
        db.query(ExportJob)
        .filter(ExportJob.status == ExportJobStatus.FAILED)
        .order_by(ExportJob.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        OpsFailedExportItem(
            id=item.id,
            report_type=item.report_type,
            format=item.format,
            status=item.status,
            created_at=item.created_at,
            error_message=item.error_message,
        )
        for item in rows
    ]


def list_failed_imports(db: Session, *, limit: int) -> list[OpsFailedReconciliationImport]:
    rows = (
        db.query(BankStatementImport)
        .filter(BankStatementImport.status == BankStatementImportStatus.FAILED)
        .order_by(BankStatementImport.uploaded_at.desc())
        .limit(limit)
        .all()
    )
    return [
        OpsFailedReconciliationImport(
            id=item.id,
            status=item.status,
            uploaded_at=item.uploaded_at,
            error=item.error,
        )
        for item in rows
    ]


def list_support_breaches(db: Session, *, limit: int) -> list[OpsSupportBreachItem]:
    rows = (
        db.query(SupportTicket)
        .filter(
            or_(
                SupportTicket.sla_first_response_status == SupportTicketSlaStatus.BREACHED,
                SupportTicket.sla_resolution_status == SupportTicketSlaStatus.BREACHED,
            )
        )
        .order_by(SupportTicket.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [
        OpsSupportBreachItem(
            id=item.id,
            status=item.status,
            priority=item.priority,
            created_at=item.created_at,
            sla_first_response_status=item.sla_first_response_status,
            sla_resolution_status=item.sla_resolution_status,
        )
        for item in rows
    ]


__all__ = [
    "build_ops_health",
    "build_ops_summary",
    "list_blocked_payouts",
    "list_failed_exports",
    "list_failed_imports",
    "list_support_breaches",
]
