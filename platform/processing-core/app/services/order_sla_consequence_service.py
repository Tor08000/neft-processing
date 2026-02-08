from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.cases import Case, CaseEventType, CaseKind, CasePriority
from app.models.internal_ledger import (
    InternalLedgerAccountType,
    InternalLedgerEntryDirection,
    InternalLedgerTransactionType,
)
from app.models.finance import CreditNote, CreditNoteStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.marketplace_contracts import Contract, ContractObligation
from app.models.marketplace_order_sla import (
    MarketplaceSlaNotificationOutbox,
    MarketplaceSlaNotificationStatus,
    OrderSlaConsequence,
    OrderSlaConsequenceStatus,
    OrderSlaConsequenceType,
    OrderSlaEvaluation,
    OrderSlaSeverity,
    OrderSlaStatus,
)
from app.models.marketplace_orders import MarketplaceOrder
from app.models.marketplace_settlement import MarketplaceAdjustmentType
from app.services.audit_service import AuditService, RequestContext
from app.services.key_normalization import normalize_key
from app.services.case_events_service import CaseEventActor, emit_case_event
from app.services.case_event_redaction import redact_deep
from app.services.decision_memory.records import record_decision_memory
from app.services.internal_ledger import InternalLedgerLine, InternalLedgerService
from app.services.marketplace_settlement_service import MarketplaceSettlementService
from app.services.partner_finance_service import PartnerFinanceService
from app.services.client_notifications import (
    ADMIN_TARGET_ROLES,
    ClientNotificationSeverity,
    create_notification,
    resolve_client_email,
)


@dataclass(frozen=True)
class OrderSlaConsequenceResult:
    consequence: OrderSlaConsequence
    was_applied: bool


def _resolve_client_id(contract: Contract) -> str | None:
    if contract.party_a_type == "client":
        return str(contract.party_a_id)
    if contract.party_b_type == "client":
        return str(contract.party_b_id)
    return None


def _resolve_partner_id(contract: Contract) -> str | None:
    if contract.party_a_type == "partner":
        return str(contract.party_a_id)
    if contract.party_b_type == "partner":
        return str(contract.party_b_id)
    return None


def _resolve_consequence_type(obligation: ContractObligation) -> OrderSlaConsequenceType:
    penalty_type = (obligation.penalty_type or "").lower()
    if penalty_type == "fee":
        return OrderSlaConsequenceType.PENALTY_FEE
    if penalty_type == "refund":
        return OrderSlaConsequenceType.REFUND
    return OrderSlaConsequenceType.CREDIT_NOTE


def _ledger_entries_for_consequence(
    *,
    consequence_type: OrderSlaConsequenceType,
    amount_minor: int,
    currency: str,
    client_id: str | None,
    partner_id: str | None,
) -> list[InternalLedgerLine]:
    if consequence_type == OrderSlaConsequenceType.PENALTY_FEE:
        return [
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.PARTNER_SETTLEMENT,
                client_id=partner_id,
                direction=InternalLedgerEntryDirection.DEBIT,
                amount=amount_minor,
                currency=currency,
                meta={"adjustment_kind": "fee"},
            ),
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.PLATFORM_FEES,
                client_id=None,
                direction=InternalLedgerEntryDirection.CREDIT,
                amount=amount_minor,
                currency=currency,
                meta={"adjustment_kind": "fee"},
            ),
        ]
    return [
        InternalLedgerLine(
            account_type=InternalLedgerAccountType.PARTNER_SETTLEMENT,
            client_id=partner_id,
            direction=InternalLedgerEntryDirection.DEBIT,
            amount=amount_minor,
            currency=currency,
            meta={"adjustment_kind": "sla_credit"},
        ),
        InternalLedgerLine(
            account_type=InternalLedgerAccountType.CLIENT_AR,
            client_id=client_id,
            direction=InternalLedgerEntryDirection.CREDIT,
            amount=amount_minor,
            currency=currency,
            meta={"adjustment_kind": "sla_credit"},
        ),
    ]


def _create_escalation_case(
    db: Session,
    *,
    order_id: str,
    severity: OrderSlaSeverity,
    request_ctx: RequestContext | None,
) -> Case:
    existing = (
        db.query(Case)
        .filter(Case.kind == CaseKind.ORDER)
        .filter(Case.entity_id == str(order_id))
        .one_or_none()
    )
    if existing:
        return existing

    case = Case(
        tenant_id=request_ctx.tenant_id if request_ctx and request_ctx.tenant_id is not None else 0,
        kind=CaseKind.ORDER,
        entity_id=str(order_id),
        kpi_key=None,
        window_days=None,
        title=f"Marketplace SLA escalation for order {order_id}",
        priority=CasePriority.CRITICAL if severity == OrderSlaSeverity.CRITICAL else CasePriority.HIGH,
        created_by=request_ctx.actor_id if request_ctx else None,
    )
    db.add(case)
    db.flush()
    emit_case_event(
        db,
        case_id=str(case.id),
        event_type=CaseEventType.SLA_ESCALATION_CASE_CREATED,
        actor=CaseEventActor(id=request_ctx.actor_id, email=request_ctx.actor_email) if request_ctx else None,
        request_id=request_ctx.request_id if request_ctx else None,
        trace_id=request_ctx.trace_id if request_ctx else None,
        extra_payload={"order_id": str(order_id), "severity": severity.value},
    )
    audit = AuditService(db).audit(
        event_type="SLA_ESCALATION_CASE_CREATED",
        entity_type="case",
        entity_id=str(case.id),
        action="SLA_ESCALATION_CASE_CREATED",
        after={"order_id": str(order_id), "severity": severity.value},
        request_ctx=request_ctx,
    )
    record_decision_memory(
        db,
        case_id=str(case.id),
        decision_type="order_sla_escalation",
        decision_ref_id=str(case.id),
        decision_at=datetime.now(timezone.utc),
        decided_by_user_id=request_ctx.actor_id if request_ctx else None,
        context_snapshot={"order_id": str(order_id), "severity": severity.value},
        rationale="SLA breach escalation triggered for marketplace order.",
        score_snapshot=None,
        mastery_snapshot=None,
        audit_event_id=str(audit.id),
    )
    return case


def _enqueue_notification(
    db: Session,
    *,
    order_id: str,
    client_id: str | None,
    partner_id: str | None,
    severity: OrderSlaSeverity,
    payload: dict[str, object],
    dedupe_key: str,
    request_ctx: RequestContext | None,
) -> None:
    redacted_payload = redact_deep(payload, "payload", include_hash=True)
    dedupe_key = normalize_key(dedupe_key, prefix="outbox:")
    existing = (
        db.query(MarketplaceSlaNotificationOutbox)
        .filter(MarketplaceSlaNotificationOutbox.dedupe_key == dedupe_key)
        .one_or_none()
    )
    if existing:
        return
    outbox = MarketplaceSlaNotificationOutbox(
        id=new_uuid_str(),
        order_id=order_id,
        client_id=client_id,
        partner_id=partner_id,
        event_type="SLA_BREACH",
        severity=severity.value,
        payload_redacted=redacted_payload,
        status=MarketplaceSlaNotificationStatus.PENDING,
        dedupe_key=dedupe_key,
    )
    db.add(outbox)
    AuditService(db).audit(
        event_type="SLA_NOTIFICATION_ENQUEUED",
        entity_type="marketplace_sla_notification_outbox",
        entity_id=str(outbox.id),
        action="SLA_NOTIFICATION_ENQUEUED",
        after={"order_id": order_id, "severity": severity.value, "dedupe_key": dedupe_key},
        request_ctx=request_ctx,
    )
    if client_id:
        email_to = resolve_client_email(db, client_id)
        create_notification(
            db,
            org_id=client_id,
            event_type="support_sla_resolution_breached",
            severity=ClientNotificationSeverity.CRITICAL,
            title="Нарушен SLA поддержки",
            body=f"Нарушен SLA по заказу {order_id}.",
            link=f"/orders/{order_id}",
            target_roles=ADMIN_TARGET_ROLES,
            entity_type="marketplace_order",
            entity_id=order_id,
            meta_json={"severity": severity.value},
            email_to=email_to,
        )


def apply_sla_consequences(
    db: Session,
    *,
    evaluation_id: str,
    request_ctx: RequestContext | None = None,
) -> OrderSlaConsequenceResult | None:
    evaluation = (
        db.query(OrderSlaEvaluation)
        .filter(OrderSlaEvaluation.id == evaluation_id)
        .one_or_none()
    )
    if not evaluation or evaluation.status != OrderSlaStatus.VIOLATION:
        return None

    obligation = db.query(ContractObligation).filter(ContractObligation.id == evaluation.obligation_id).one()
    contract = db.query(Contract).filter(Contract.id == evaluation.contract_id).one()
    consequence_type = _resolve_consequence_type(obligation)
    dedupe_key_raw = (
        f"order:{evaluation.order_id}:obligation:{obligation.id}:period:{evaluation.period_end.isoformat()}"
    )
    dedupe_key = normalize_key(dedupe_key_raw, prefix="dedupe:")
    existing = (
        db.query(OrderSlaConsequence)
        .filter(OrderSlaConsequence.dedupe_key == dedupe_key)
        .one_or_none()
    )
    if existing:
        return OrderSlaConsequenceResult(consequence=existing, was_applied=False)

    amount = Decimal(str(obligation.penalty_value))
    if amount <= 0:
        return None
    if amount != amount.to_integral_value():
        raise ValueError("penalty_amount_must_be_integer")
    amount_minor = int(amount)

    client_id = _resolve_client_id(contract)
    partner_id = _resolve_partner_id(contract)
    ledger_service = InternalLedgerService(db)
    consequence_id = new_uuid_str()
    ledger_result = ledger_service.post_transaction(
        tenant_id=request_ctx.tenant_id if request_ctx and request_ctx.tenant_id is not None else 0,
        transaction_type=InternalLedgerTransactionType.ADJUSTMENT,
        external_ref_type="ORDER_SLA_CONSEQUENCE",
        external_ref_id=consequence_id,
        idempotency_key=normalize_key(f"order_sla:{dedupe_key}", prefix="ledger:"),
        posted_at=datetime.now(timezone.utc),
        meta={
            "order_id": evaluation.order_id,
            "evaluation_id": str(evaluation.id),
            "obligation_id": str(obligation.id),
            "consequence_type": consequence_type.value,
        },
        entries=_ledger_entries_for_consequence(
            consequence_type=consequence_type,
            amount_minor=amount_minor,
            currency=contract.currency,
            client_id=client_id,
            partner_id=partner_id,
        ),
    )

    audit = AuditService(db).audit(
        event_type="SLA_CONSEQUENCE_APPLIED",
        entity_type="order_sla_consequence",
        entity_id=consequence_id,
        action="SLA_CONSEQUENCE_APPLIED",
        after={
            "order_id": evaluation.order_id,
            "evaluation_id": str(evaluation.id),
            "consequence_type": consequence_type.value,
            "amount": str(amount),
            "currency": contract.currency,
            "ledger_tx_id": str(ledger_result.transaction.id),
        },
        request_ctx=request_ctx,
    )
    consequence = OrderSlaConsequence(
        id=consequence_id,
        order_id=evaluation.order_id,
        evaluation_id=evaluation.id,
        consequence_type=consequence_type,
        amount=amount,
        currency=contract.currency,
        ledger_tx_id=ledger_result.transaction.id,
        status=OrderSlaConsequenceStatus.APPLIED,
        dedupe_key=dedupe_key,
        audit_event_id=audit.id,
    )
    db.add(consequence)

    record_decision_memory(
        db,
        case_id=None,
        decision_type="order_sla_consequence",
        decision_ref_id=consequence_id,
        decision_at=datetime.now(timezone.utc),
        decided_by_user_id=request_ctx.actor_id if request_ctx else None,
        context_snapshot={
            "order_id": evaluation.order_id,
            "evaluation_id": str(evaluation.id),
            "consequence_type": consequence_type.value,
            "amount": str(amount),
            "currency": contract.currency,
        },
        rationale=f"SLA consequence applied for order {evaluation.order_id}",
        score_snapshot=None,
        mastery_snapshot=None,
        audit_event_id=str(audit.id),
    )

    severity = evaluation.breach_severity or OrderSlaSeverity.MEDIUM
    payload = {
        "order_id": evaluation.order_id,
        "evaluation_id": str(evaluation.id),
        "consequence_id": consequence_id,
        "consequence_type": consequence_type.value,
        "amount": str(amount),
        "currency": contract.currency,
        "severity": severity.value,
    }
    if client_id:
        dedupe_key = normalize_key(
            f"order:{evaluation.order_id}:eval:{evaluation.id}:client:{client_id}",
            prefix="outbox:",
        )
        _enqueue_notification(
            db,
            order_id=evaluation.order_id,
            client_id=client_id,
            partner_id=None,
            severity=severity,
            payload=payload,
            dedupe_key=dedupe_key,
            request_ctx=request_ctx,
        )
    if partner_id:
        dedupe_key = normalize_key(
            f"order:{evaluation.order_id}:eval:{evaluation.id}:partner:{partner_id}",
            prefix="outbox:",
        )
        _enqueue_notification(
            db,
            order_id=evaluation.order_id,
            client_id=None,
            partner_id=partner_id,
            severity=severity,
            payload=payload,
            dedupe_key=dedupe_key,
            request_ctx=request_ctx,
        )

    if severity in {OrderSlaSeverity.HIGH, OrderSlaSeverity.CRITICAL}:
        _create_escalation_case(
            db,
            order_id=evaluation.order_id,
            severity=severity,
            request_ctx=request_ctx,
        )

    _apply_marketplace_penalty(
        db,
        evaluation=evaluation,
        consequence=consequence,
        amount=amount,
        request_ctx=request_ctx,
    )

    return OrderSlaConsequenceResult(consequence=consequence, was_applied=True)


def _apply_marketplace_penalty(
    db: Session,
    *,
    evaluation: OrderSlaEvaluation,
    consequence: OrderSlaConsequence,
    amount: Decimal,
    request_ctx: RequestContext | None,
) -> None:
    order = db.query(MarketplaceOrder).filter(MarketplaceOrder.id == evaluation.order_id).one_or_none()
    if not order:
        return
    settlement_service = MarketplaceSettlementService(db, request_ctx=request_ctx)
    period = None
    if order.completed_at:
        period = order.completed_at.strftime("%Y-%m")
    elif order.created_at:
        period = order.created_at.strftime("%Y-%m")
    else:
        period = datetime.now(timezone.utc).strftime("%Y-%m")
    adjustment = settlement_service.apply_adjustment(
        partner_id=str(order.partner_id),
        order_id=str(order.id),
        period=period,
        adjustment_type=MarketplaceAdjustmentType.PENALTY,
        amount=amount,
        reason_code=f"SLA_BREACH_{evaluation.breach_reason or 'UNKNOWN'}",
        meta={"evaluation_id": str(evaluation.id), "consequence_id": str(consequence.id)},
    )
    penalty_result = settlement_service.update_penalty_for_order(order_id=str(order.id), penalty_amount=amount)
    if penalty_result and penalty_result.clawback_required:
        adjustment.meta = {**(adjustment.meta or {}), "clawback_required": True}
    PartnerFinanceService(db, request_ctx=request_ctx).record_sla_penalty(
        partner_org_id=str(order.partner_id),
        order_id=str(order.id),
        amount=amount,
        currency=order.currency or consequence.currency or "RUB",
        reason=f"SLA_BREACH_{evaluation.breach_reason or 'UNKNOWN'}",
    )
    AuditService(db).audit(
        event_type="MARKETPLACE_SLA_PENALTY_APPLIED",
        entity_type="marketplace_adjustment",
        entity_id=str(adjustment.id),
        action="MARKETPLACE_SLA_PENALTY_APPLIED",
        after={
            "order_id": str(order.id),
            "partner_id": str(order.partner_id),
            "amount": str(amount),
            "currency": order.currency,
        },
        request_ctx=request_ctx,
    )
    _maybe_create_credit_note(
        db,
        order=order,
        amount=amount,
        currency=order.currency or consequence.currency,
        evaluation=evaluation,
        request_ctx=request_ctx,
    )


def _maybe_create_credit_note(
    db: Session,
    *,
    order: MarketplaceOrder,
    amount: Decimal,
    currency: str | None,
    evaluation: OrderSlaEvaluation,
    request_ctx: RequestContext | None,
) -> None:
    invoice = (
        db.query(Invoice)
        .filter(Invoice.client_id == str(order.client_id))
        .filter(Invoice.currency == (currency or "RUB"))
        .filter(Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID]))
        .order_by(Invoice.period_to.desc())
        .first()
    )
    if not invoice:
        return
    idempotency_key = normalize_key(
        f"sla_credit:{order.id}:{evaluation.id}:{invoice.id}",
        prefix="credit_note:",
    )
    existing = db.query(CreditNote).filter(CreditNote.idempotency_key == idempotency_key).one_or_none()
    if existing:
        return
    credit_note = CreditNote(
        id=new_uuid_str(),
        invoice_id=str(invoice.id),
        amount=int(amount),
        currency=currency or invoice.currency,
        reason="sla_penalty",
        idempotency_key=idempotency_key,
        status=CreditNoteStatus.POSTED,
    )
    db.add(credit_note)
    AuditService(db).audit(
        event_type="BILLING_CREDIT_NOTE_CREATED",
        entity_type="credit_note",
        entity_id=str(credit_note.id),
        action="BILLING_CREDIT_NOTE_CREATED",
        after={
            "order_id": str(order.id),
            "invoice_id": str(invoice.id),
            "amount": str(amount),
            "currency": currency or invoice.currency,
            "reason": "sla_penalty",
        },
        request_ctx=request_ctx,
    )


__all__ = ["OrderSlaConsequenceResult", "apply_sla_consequences"]
