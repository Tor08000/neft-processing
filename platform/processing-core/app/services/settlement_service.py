from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.audit_log import AuditVisibility
from app.models.cases import Case, CaseEventType, CaseKind, CasePriority
from app.models.internal_ledger import (
    InternalLedgerAccountType,
    InternalLedgerEntry,
    InternalLedgerEntryDirection,
    InternalLedgerTransaction,
    InternalLedgerTransactionType,
)
from app.models.reconciliation import (
    ReconciliationLink,
    ReconciliationLinkDirection,
    ReconciliationLinkStatus,
)
from app.models.settlement_v1 import (
    PayoutStatus,
    SettlementAccount,
    SettlementAccountStatus,
    SettlementItem,
    SettlementItemDirection,
    SettlementItemSourceType,
    SettlementPeriod,
    SettlementPeriodStatus,
    SettlementPayout,
)
from app.services.audit_service import AuditService, RequestContext
from app.services.case_events_service import CaseEventActor, emit_case_event
from app.services.decision_memory.records import record_decision_memory
from app.services.internal_ledger import InternalLedgerLine, InternalLedgerService


class SettlementServiceError(Exception):
    """Domain error for settlement lifecycle violations."""


@dataclass(frozen=True)
class SettlementTotals:
    total_gross: Decimal
    total_fees: Decimal
    total_refunds: Decimal
    net_amount: Decimal


def _normalize_currency(currency: str) -> str:
    return currency.upper()


def _amount_to_minor(amount: Decimal) -> int:
    return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _amount_from_minor(amount_minor: int) -> Decimal:
    return (Decimal(amount_minor) / Decimal("100")).quantize(Decimal("0.01"))


def apply_order_penalty(
    db: Session,
    *,
    order_id: str,
    amount_minor: int,
    currency: str,
    partner_id: str,
    actor: RequestContext | None,
    idempotency_key: str | None = None,
) -> InternalLedgerTransaction:
    if amount_minor <= 0:
        raise SettlementServiceError("invalid_penalty_amount")
    ledger_service = InternalLedgerService(db)
    result = ledger_service.post_transaction(
        tenant_id=actor.tenant_id if actor and actor.tenant_id is not None else 0,
        transaction_type=InternalLedgerTransactionType.ADJUSTMENT,
        external_ref_type="ORDER_PENALTY",
        external_ref_id=order_id,
        idempotency_key=idempotency_key or f"order_penalty:{order_id}",
        posted_at=datetime.now(timezone.utc),
        meta={"order_id": order_id, "adjustment_kind": "sla_penalty"},
        entries=[
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.PARTNER_SETTLEMENT,
                client_id=partner_id,
                direction=InternalLedgerEntryDirection.DEBIT,
                amount=amount_minor,
                currency=currency,
                meta={"adjustment_kind": "sla_penalty"},
            ),
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.PLATFORM_FEES,
                client_id=None,
                direction=InternalLedgerEntryDirection.CREDIT,
                amount=amount_minor,
                currency=currency,
                meta={"adjustment_kind": "sla_penalty"},
            ),
        ],
    )
    return result.transaction


def _resolve_source(entry: InternalLedgerEntry, transaction: InternalLedgerTransaction) -> tuple[str, str]:
    meta = entry.meta or {}
    source_type = meta.get("source_type")
    source_id = meta.get("source_id")
    if source_type and source_id:
        return str(source_type), str(source_id)
    external_ref_type = transaction.external_ref_type
    external_ref_id = transaction.external_ref_id
    if external_ref_type == "BILLING_INVOICE":
        return SettlementItemSourceType.INVOICE.value, str(external_ref_id)
    if external_ref_type == "BILLING_PAYMENT":
        return SettlementItemSourceType.PAYMENT.value, str(external_ref_id)
    if external_ref_type == "BILLING_REFUND":
        return SettlementItemSourceType.REFUND.value, str(external_ref_id)
    if transaction.transaction_type == InternalLedgerTransactionType.ADJUSTMENT:
        return SettlementItemSourceType.ADJUSTMENT.value, str(external_ref_id)
    return SettlementItemSourceType.ADJUSTMENT.value, str(external_ref_id)


def _is_fee_adjustment(entry: InternalLedgerEntry) -> bool:
    meta = entry.meta or {}
    return str(meta.get("adjustment_kind") or "").lower() in {"fee", "fees", "commission"}


def _settlement_case(
    db: Session,
    *,
    tenant_id: int,
    period_id: str,
    actor: RequestContext | None,
) -> Case:
    existing = (
        db.query(Case)
        .filter(Case.kind == CaseKind.ORDER)
        .filter(Case.entity_id == str(period_id))
        .one_or_none()
    )
    if existing:
        return existing
    case = Case(
        tenant_id=tenant_id,
        kind=CaseKind.ORDER,
        entity_id=str(period_id),
        kpi_key=None,
        window_days=None,
        title=f"Settlement period {period_id}",
        priority=CasePriority.MEDIUM,
        created_by=actor.actor_id if actor else None,
    )
    db.add(case)
    db.flush()
    return case


def _emit_case_event(
    db: Session,
    *,
    case: Case,
    event_type: CaseEventType,
    actor: RequestContext | None,
    payload: dict[str, object],
) -> str:
    event = emit_case_event(
        db,
        case_id=str(case.id),
        event_type=event_type,
        actor=CaseEventActor(id=actor.actor_id, email=actor.actor_email) if actor else None,
        request_id=actor.request_id if actor else None,
        trace_id=actor.trace_id if actor else None,
        extra_payload=payload,
    )
    return str(event.id)


def _write_decision_memory(
    db: Session,
    *,
    case_id: str,
    decision_type: str,
    decision_ref_id: str,
    decision_at: datetime,
    decided_by_user_id: str | None,
    context_snapshot: dict[str, object],
    rationale: str,
    audit_event_id: str,
) -> None:
    record_decision_memory(
        db,
        case_id=case_id,
        decision_type=decision_type,
        decision_ref_id=decision_ref_id,
        decision_at=decision_at,
        decided_by_user_id=decided_by_user_id,
        context_snapshot=context_snapshot,
        rationale=rationale,
        score_snapshot=None,
        mastery_snapshot=None,
        audit_event_id=audit_event_id,
    )


def calculate_settlement_period(
    db: Session,
    *,
    partner_id: str,
    currency: str,
    period_start: datetime,
    period_end: datetime,
    actor: RequestContext | None,
    idempotency_key: str,
) -> SettlementPeriod:
    if period_start >= period_end:
        raise SettlementServiceError("invalid_period")

    currency_code = _normalize_currency(currency)
    tenant_id = actor.tenant_id if actor and actor.tenant_id is not None else 0

    overlap = (
        db.query(SettlementPeriod)
        .filter(SettlementPeriod.partner_id == partner_id)
        .filter(SettlementPeriod.currency == currency_code)
        .filter(SettlementPeriod.status.in_([SettlementPeriodStatus.APPROVED, SettlementPeriodStatus.PAID]))
        .filter(and_(SettlementPeriod.period_start <= period_end, SettlementPeriod.period_end >= period_start))
        .first()
    )
    if overlap:
        raise SettlementServiceError("period_overlap")

    existing = (
        db.query(SettlementPeriod)
        .filter(SettlementPeriod.partner_id == partner_id)
        .filter(SettlementPeriod.currency == currency_code)
        .filter(SettlementPeriod.period_start == period_start)
        .filter(SettlementPeriod.period_end == period_end)
        .one_or_none()
    )
    if existing:
        return existing

    account = (
        db.query(SettlementAccount)
        .filter(SettlementAccount.partner_id == partner_id)
        .filter(SettlementAccount.currency == currency_code)
        .one_or_none()
    )
    if not account:
        account = SettlementAccount(
            partner_id=partner_id,
            currency=currency_code,
            status=SettlementAccountStatus.ACTIVE,
        )
        db.add(account)

    entries_query = (
        db.query(InternalLedgerEntry, InternalLedgerTransaction, InternalLedgerAccount)
        .join(InternalLedgerTransaction, InternalLedgerEntry.ledger_transaction_id == InternalLedgerTransaction.id)
        .join(InternalLedgerAccount, InternalLedgerEntry.account_id == InternalLedgerAccount.id)
        .filter(InternalLedgerAccount.account_type == InternalLedgerAccountType.PARTNER_SETTLEMENT)
        .filter(InternalLedgerAccount.client_id == partner_id)
        .filter(InternalLedgerEntry.currency == currency_code)
        .filter(InternalLedgerEntry.created_at >= period_start)
        .filter(InternalLedgerEntry.created_at <= period_end)
    )
    if tenant_id:
        entries_query = entries_query.filter(InternalLedgerEntry.tenant_id == tenant_id)
    ledger_rows = entries_query.all()

    items: list[SettlementItem] = []
    total_gross = Decimal("0")
    total_fees = Decimal("0")
    total_refunds = Decimal("0")
    adjustments_net = Decimal("0")
    for entry, transaction, _account in ledger_rows:
        source_type_value, source_id_value = _resolve_source(entry, transaction)
        direction = (
            SettlementItemDirection.IN
            if entry.direction == InternalLedgerEntryDirection.CREDIT
            else SettlementItemDirection.OUT
        )
        amount = _amount_from_minor(int(entry.amount))
        item = SettlementItem(
            settlement_period_id=None,
            source_type=SettlementItemSourceType(source_type_value),
            source_id=source_id_value,
            amount=amount,
            direction=direction,
        )
        items.append(item)
        if item.source_type in {SettlementItemSourceType.INVOICE, SettlementItemSourceType.PAYMENT}:
            if direction == SettlementItemDirection.IN:
                total_gross += amount
        elif item.source_type == SettlementItemSourceType.REFUND:
            total_refunds += amount
        elif item.source_type == SettlementItemSourceType.ADJUSTMENT:
            if _is_fee_adjustment(entry):
                total_fees += amount
            else:
                adjustments_net += amount if direction == SettlementItemDirection.IN else amount * Decimal("-1")

    totals = SettlementTotals(
        total_gross=total_gross,
        total_fees=total_fees,
        total_refunds=total_refunds,
        net_amount=total_gross - total_fees - total_refunds + adjustments_net,
    )
    period = SettlementPeriod(
        partner_id=partner_id,
        currency=currency_code,
        period_start=period_start,
        period_end=period_end,
        status=SettlementPeriodStatus.CALCULATED,
        total_gross=totals.total_gross,
        total_fees=totals.total_fees,
        total_refunds=totals.total_refunds,
        net_amount=totals.net_amount,
    )
    db.add(period)
    db.flush()

    for item in items:
        item.settlement_period_id = period.id
        db.add(item)

    audit_event = AuditService(db).audit(
        event_type="SETTLEMENT_CALCULATED",
        entity_type="settlement_period",
        entity_id=str(period.id),
        action="CALCULATE",
        visibility=AuditVisibility.INTERNAL,
        after={
            "partner_id": partner_id,
            "currency": currency_code,
            "period_start": period_start,
            "period_end": period_end,
            "total_gross": str(totals.total_gross),
            "total_fees": str(totals.total_fees),
            "total_refunds": str(totals.total_refunds),
            "net_amount": str(totals.net_amount),
            "idempotency_key": idempotency_key,
        },
        request_ctx=actor,
    )
    period.audit_event_id = audit_event.id

    case = _settlement_case(db, tenant_id=tenant_id, period_id=str(period.id), actor=actor)
    case_event_id = _emit_case_event(
        db,
        case=case,
        event_type=CaseEventType.SETTLEMENT_CALCULATED,
        actor=actor,
        payload={
            "settlement_period_id": str(period.id),
            "net_amount": str(totals.net_amount),
            "currency": currency_code,
        },
    )
    _write_decision_memory(
        db,
        case_id=str(case.id),
        decision_type="settlement_calculated",
        decision_ref_id=str(period.id),
        decision_at=datetime.now(timezone.utc),
        decided_by_user_id=actor.actor_id if actor else None,
        context_snapshot={
            "settlement_period_id": str(period.id),
            "total_gross": str(totals.total_gross),
            "total_fees": str(totals.total_fees),
            "total_refunds": str(totals.total_refunds),
            "net_amount": str(totals.net_amount),
        },
        rationale=f"Settlement calculated for partner {partner_id}",
        audit_event_id=case_event_id,
    )
    return period


def approve_settlement(
    db: Session,
    *,
    period_id: str,
    actor: RequestContext | None,
) -> SettlementPeriod:
    period = db.query(SettlementPeriod).filter(SettlementPeriod.id == period_id).one_or_none()
    if period is None:
        raise SettlementServiceError("settlement_period_not_found")
    if period.status != SettlementPeriodStatus.CALCULATED:
        raise SettlementServiceError("settlement_period_not_calculated")

    now = datetime.now(timezone.utc)
    period.status = SettlementPeriodStatus.APPROVED
    period.approved_at = now

    audit_event = AuditService(db).audit(
        event_type="SETTLEMENT_APPROVED",
        entity_type="settlement_period",
        entity_id=str(period.id),
        action="APPROVE",
        visibility=AuditVisibility.INTERNAL,
        after={
            "status": period.status.value,
            "approved_at": period.approved_at,
        },
        request_ctx=actor,
    )
    period.audit_event_id = audit_event.id

    tenant_id = actor.tenant_id if actor and actor.tenant_id is not None else 0
    case = _settlement_case(db, tenant_id=tenant_id, period_id=str(period.id), actor=actor)
    case_event_id = _emit_case_event(
        db,
        case=case,
        event_type=CaseEventType.SETTLEMENT_APPROVED,
        actor=actor,
        payload={
            "settlement_period_id": str(period.id),
            "approved_at": now.isoformat(),
        },
    )
    _write_decision_memory(
        db,
        case_id=str(case.id),
        decision_type="settlement_approved",
        decision_ref_id=str(period.id),
        decision_at=now,
        decided_by_user_id=actor.actor_id if actor else None,
        context_snapshot={"settlement_period_id": str(period.id), "status": period.status.value},
        rationale=f"Settlement approved for partner {period.partner_id}",
        audit_event_id=case_event_id,
    )
    return period


def execute_payout(
    db: Session,
    *,
    period_id: str,
    provider: str,
    idempotency_key: str,
    actor: RequestContext | None,
) -> SettlementPayout:
    period = db.query(SettlementPeriod).filter(SettlementPeriod.id == period_id).one_or_none()
    if period is None:
        raise SettlementServiceError("settlement_period_not_found")
    if period.status != SettlementPeriodStatus.APPROVED:
        raise SettlementServiceError("settlement_period_not_approved")

    existing = db.query(SettlementPayout).filter(SettlementPayout.idempotency_key == idempotency_key).one_or_none()
    if existing:
        if existing.settlement_period_id != period.id:
            raise SettlementServiceError("idempotency_conflict")
        return existing

    existing_for_period = (
        db.query(SettlementPayout)
        .filter(SettlementPayout.settlement_period_id == period.id)
        .one_or_none()
    )
    if existing_for_period:
        raise SettlementServiceError("payout_already_exists")

    amount = Decimal(period.net_amount)
    if amount <= Decimal("0"):
        raise SettlementServiceError("payout_amount_invalid")

    now = datetime.now(timezone.utc)
    payout = SettlementPayout(
        settlement_period_id=period.id,
        partner_id=period.partner_id,
        currency=period.currency,
        amount=amount,
        status=PayoutStatus.INITIATED,
        provider=provider,
        provider_payout_id=None,
        idempotency_key=idempotency_key,
    )
    db.add(payout)
    db.flush()

    ledger_service = InternalLedgerService(db)
    amount_minor = _amount_to_minor(amount)
    ledger_result = ledger_service.post_transaction(
        tenant_id=actor.tenant_id if actor and actor.tenant_id is not None else 0,
        transaction_type=InternalLedgerTransactionType.PARTNER_PAYOUT,
        external_ref_type="PARTNER_PAYOUT",
        external_ref_id=str(payout.id),
        idempotency_key=f"settlement:payout:{idempotency_key}",
        posted_at=now,
        meta={"payout_id": str(payout.id), "settlement_period_id": str(period.id)},
        entries=[
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.PARTNER_SETTLEMENT,
                client_id=str(period.partner_id),
                direction=InternalLedgerEntryDirection.DEBIT,
                amount=amount_minor,
                currency=period.currency,
                meta={"payout_id": str(payout.id)},
            ),
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.SETTLEMENT_CLEARING,
                client_id=None,
                direction=InternalLedgerEntryDirection.CREDIT,
                amount=amount_minor,
                currency=period.currency,
                meta={"payout_id": str(payout.id)},
            ),
        ],
    )
    payout.ledger_tx_id = ledger_result.transaction.id

    link = ReconciliationLink(
        entity_type="payout",
        entity_id=payout.id,
        provider=provider,
        currency=period.currency,
        expected_amount=amount,
        direction=ReconciliationLinkDirection.OUT,
        expected_at=now,
        match_key=None,
        status=ReconciliationLinkStatus.PENDING,
    )
    db.add(link)
    db.flush()

    audit_event = AuditService(db).audit(
        event_type="PAYOUT_INITIATED",
        entity_type="payout",
        entity_id=str(payout.id),
        action="INITIATE",
        visibility=AuditVisibility.INTERNAL,
        after={
            "settlement_period_id": str(period.id),
            "amount": str(amount),
            "currency": period.currency,
            "provider": provider,
            "ledger_tx_id": str(ledger_result.transaction.id),
            "reconciliation_link_id": str(link.id),
        },
        request_ctx=actor,
    )
    payout.audit_event_id = audit_event.id
    payout.status = PayoutStatus.SENT

    period.status = SettlementPeriodStatus.PAID
    period.paid_at = now

    tenant_id = actor.tenant_id if actor and actor.tenant_id is not None else 0
    case = _settlement_case(db, tenant_id=tenant_id, period_id=str(period.id), actor=actor)
    case_event_id = _emit_case_event(
        db,
        case=case,
        event_type=CaseEventType.PAYOUT_INITIATED,
        actor=actor,
        payload={
            "settlement_period_id": str(period.id),
            "payout_id": str(payout.id),
            "amount": str(amount),
            "currency": period.currency,
        },
    )
    _write_decision_memory(
        db,
        case_id=str(case.id),
        decision_type="payout_initiated",
        decision_ref_id=str(payout.id),
        decision_at=now,
        decided_by_user_id=actor.actor_id if actor else None,
        context_snapshot={
            "payout_id": str(payout.id),
            "settlement_period_id": str(period.id),
            "amount": str(amount),
            "currency": period.currency,
        },
        rationale=f"Payout initiated for partner {period.partner_id}",
        audit_event_id=case_event_id,
    )
    return payout
