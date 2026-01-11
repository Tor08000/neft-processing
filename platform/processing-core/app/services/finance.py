from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Tuple

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.billing_job_run import BillingJobStatus, BillingJobType
from app.models.billing_period import BillingPeriod, BillingPeriodStatus
from app.models.finance import (
    CreditNote,
    CreditNoteStatus,
    InvoicePayment,
    InvoiceSettlementAllocation,
    PaymentStatus,
    SettlementSourceType,
)
from app.models.internal_ledger import InternalLedgerTransaction
from app.models.invoice import Invoice, InvoiceStatus
from app.models.money_flow import MoneyFlowEvent
from app.models.refund_request import RefundRequest
from app.services.legal_graph import (
    GraphContext,
    LegalGraphBuilder,
    LegalGraphWriteFailure,
    audit_graph_write_failure,
)
from neft_shared.logging_setup import get_logger
from app.services.internal_ledger import InternalLedgerService
from app.services.billing_metrics import metrics as billing_metrics
from app.services.billing_job_runs import BillingJobRunService
from app.services.job_locks import advisory_lock, make_lock_token
from app.services.audit_service import RequestContext
from app.services.audit_service import AuditService
from app.services.decision import DecisionAction, DecisionContext, DecisionEngine, DecisionOutcome
from app.services.invoice_state_machine import InvoiceStateMachine, InvalidTransitionError, InvoiceInvariantError
from app.services.policy import Action, PolicyAccessDenied, PolicyEngine, actor_from_token, audit_access_denied
from app.services.policy.resources import ResourceContext
from app.services.settlement_allocations import resolve_settlement_period
from app.services.finance_invariants import FinancialInvariantChecker, FinancialInvariantViolation
from app.services.money_flow.events import MoneyFlowEventType
from app.services.money_flow.states import MoneyFlowState, MoneyFlowType

logger = get_logger(__name__)

class FinanceOperationInProgress(RuntimeError):
    """Finance operation already running for the requested invoice."""


class InvoiceNotFound(RuntimeError):
    """Invoice missing for finance operation."""


class PaymentReferenceConflict(RuntimeError):
    """Payment external reference points to a different invoice."""


class PaymentIdempotencyConflict(RuntimeError):
    """Payment idempotency key reused with a different payload."""


class RefundReferenceConflict(RuntimeError):
    """Refund external reference points to a different invoice."""


@dataclass
class PaymentResult:
    payment: InvoicePayment
    invoice: Invoice
    is_replay: bool = False


@dataclass
class CreditNoteResult:
    credit_note: CreditNote
    invoice: Invoice
    is_replay: bool = False


class FinanceService:
    """Handle finance operations (payments, credit notes) with idempotency."""

    def __init__(self, db: Session):
        self.db = db
        self.job_service = BillingJobRunService(db)
        self.policy_engine = PolicyEngine()
        self.invariant_checker = FinancialInvariantChecker(db)

    @staticmethod
    def _normalize_idempotency_key(idempotency_key: str) -> str:
        if len(idempotency_key) <= 128:
            return idempotency_key
        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        return f"hash:{digest}"

    def _audit_invariant_violation(
        self,
        violation: FinancialInvariantViolation,
        *,
        request_ctx: RequestContext | None,
        extra_payload: dict | None = None,
    ) -> None:
        self.invariant_checker.audit_violation(
            violation,
            request_ctx=request_ctx,
            extra_payload=extra_payload,
        )
        self.db.commit()

    def _lock_invoice(self, invoice_id: str) -> Invoice:
        stmt = select(Invoice).where(Invoice.id == invoice_id)
        dialect = getattr(self.db.bind, "dialect", None)
        if dialect and dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        invoice = self.db.execute(stmt).scalar_one_or_none()
        if not invoice:
            raise InvoiceNotFound(invoice_id)
        return invoice

    def _require_settlement_period(self, invoice: Invoice, *, action: str) -> None:
        if not invoice.billing_period_id:
            return
        period = (
            self.db.query(BillingPeriod)
            .filter(BillingPeriod.id == invoice.billing_period_id)
            .one_or_none()
        )
        if not period:
            raise InvalidTransitionError("billing period not found")
        if period.status not in {BillingPeriodStatus.FINALIZED, BillingPeriodStatus.LOCKED}:
            raise InvalidTransitionError(f"billing period {period.id} is {period.status.value} for {action}")

    def _resolve_existing_payment(
        self,
        *,
        invoice_id: str,
        idempotency_key: str,
        external_ref: str | None,
        provider: str | None,
    ) -> InvoicePayment | None:
        try:
            if external_ref:
                query = self.db.query(InvoicePayment).filter(InvoicePayment.external_ref == external_ref)
                if provider is None:
                    query = query.filter(InvoicePayment.provider.is_(None))
                else:
                    query = query.filter(InvoicePayment.provider == provider)
                existing_by_ref = query.one_or_none()
                if existing_by_ref:
                    if existing_by_ref.invoice_id != invoice_id:
                        billing_metrics.mark_payment_error()
                        billing_metrics.mark_payment_failed()
                        raise PaymentReferenceConflict(external_ref)
                    return existing_by_ref

            existing = (
                self.db.query(InvoicePayment)
                .filter(InvoicePayment.idempotency_key == idempotency_key)
                .one_or_none()
            )
            if existing and existing.invoice_id != invoice_id:
                billing_metrics.mark_payment_error()
                billing_metrics.mark_payment_failed()
                raise PaymentReferenceConflict(idempotency_key)
            return existing
        except (DBAPIError, SQLAlchemyError):
            self.db.rollback()
            logger.exception("payment_lookup_failed", extra={"idempotency_key": idempotency_key})
            raise

    def _resolve_payment_money_flow_event(self, *, idempotency_key: str) -> MoneyFlowEvent | None:
        return (
            self.db.query(MoneyFlowEvent)
            .filter(MoneyFlowEvent.idempotency_key == idempotency_key)
            .one_or_none()
        )

    def _resolve_payment_from_event(
        self,
        *,
        event: MoneyFlowEvent,
        idempotency_key: str,
    ) -> InvoicePayment | None:
        payment_id = None
        if event.meta:
            payment_id = event.meta.get("payment_id")
        if payment_id:
            payment = (
                self.db.query(InvoicePayment)
                .filter(InvoicePayment.id == payment_id)
                .one_or_none()
            )
            if payment:
                return payment
        return (
            self.db.query(InvoicePayment)
            .filter(InvoicePayment.idempotency_key == idempotency_key)
            .one_or_none()
        )

    def _replay_from_money_flow_event(
        self,
        *,
        invoice_id: str,
        idempotency_key: str,
        amount: int,
        currency: str,
        external_ref: str | None,
        provider: str | None,
        request_ctx: RequestContext | None,
        token: dict | None,
    ) -> PaymentResult | None:
        try:
            event = self._resolve_payment_money_flow_event(idempotency_key=idempotency_key)
            if not event:
                return None
            payment = self._resolve_payment_from_event(event=event, idempotency_key=idempotency_key)
            if payment is None:
                logger.warning(
                    "money_flow_event_missing_payment",
                    extra={"idempotency_key": idempotency_key, "event_id": str(event.id)},
                )
                return None
            if payment.invoice_id != invoice_id:
                billing_metrics.mark_payment_error()
                billing_metrics.mark_payment_failed()
                raise PaymentReferenceConflict(idempotency_key)
            invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
            if not invoice:
                raise InvoiceNotFound(invoice_id)
            self._validate_payment_replay(
                payment=payment,
                amount=amount,
                currency=currency,
                external_ref=external_ref,
                provider=provider,
            )
            return PaymentResult(payment=payment, invoice=invoice, is_replay=True)
        except (DBAPIError, SQLAlchemyError):
            self.db.rollback()
            logger.exception("payment_replay_lookup_failed", extra={"idempotency_key": idempotency_key})
            raise

    def _ensure_payment_money_flow_event(
        self,
        *,
        invoice: Invoice,
        payment: InvoicePayment,
        tenant_id: int,
        ledger_transaction_id: str | None,
        idempotency_key: str,
    ) -> tuple[MoneyFlowEvent, bool]:
        existing = self._resolve_payment_money_flow_event(idempotency_key=idempotency_key)
        if existing:
            return existing, False
        event = MoneyFlowEvent(
            tenant_id=tenant_id,
            client_id=invoice.client_id,
            flow_type=MoneyFlowType.INVOICE_PAYMENT,
            flow_ref_id=invoice.id,
            state_from=None,
            state_to=MoneyFlowState.SETTLED,
            event_type=MoneyFlowEventType.SETTLE,
            idempotency_key=idempotency_key,
            ledger_transaction_id=ledger_transaction_id,
            meta={"invoice_id": invoice.id, "payment_id": str(payment.id)},
        )
        try:
            nested = self.db.begin_nested()
            self.db.add(event)
            self.db.flush()
            nested.commit()
        except IntegrityError:
            nested.rollback()
            existing = self._resolve_payment_money_flow_event(idempotency_key=idempotency_key)
            if existing:
                return existing, False
            raise
        return event, True

    def _validate_payment_replay(
        self,
        *,
        payment: InvoicePayment,
        amount: int,
        currency: str,
        external_ref: str | None,
        provider: str | None,
    ) -> None:
        if int(payment.amount) != int(amount):
            raise PaymentIdempotencyConflict("amount_mismatch")
        if payment.currency != currency:
            raise PaymentIdempotencyConflict("currency_mismatch")
        if (payment.external_ref or None) != (external_ref or None):
            raise PaymentIdempotencyConflict("external_ref_mismatch")
        if (payment.provider or None) != (provider or None):
            raise PaymentIdempotencyConflict("provider_mismatch")

    def _replay_payment(
        self,
        *,
        invoice_id: str,
        payment: InvoicePayment,
        request_ctx: RequestContext | None,
        token: dict | None,
        invoice: Invoice | None = None,
    ) -> PaymentResult:
        invoice = invoice or self._lock_invoice(invoice_id)
        self._enforce_policy(token=token, action=Action.PAYMENT_APPLY, invoice=invoice)
        if self._payment_already_applied(invoice=invoice, payment=payment):
            return PaymentResult(payment=payment, invoice=invoice, is_replay=True)
        InternalLedgerService(self.db).post_payment_applied(
            invoice=invoice,
            payment=payment,
            tenant_id=self._resolve_tenant_id(request_ctx),
        )
        self._ensure_settlement_allocation(
            invoice=invoice,
            source_type=SettlementSourceType.PAYMENT,
            source_id=str(payment.id),
            amount=int(payment.amount),
            currency=payment.currency,
            applied_at=payment.created_at,
            request_ctx=request_ctx,
        )
        return PaymentResult(payment=payment, invoice=invoice, is_replay=True)

    def _payment_already_applied(self, *, invoice: Invoice, payment: InvoicePayment) -> bool:
        allocation_exists = (
            self.db.query(InvoiceSettlementAllocation.id)
            .filter(InvoiceSettlementAllocation.invoice_id == invoice.id)
            .filter(InvoiceSettlementAllocation.source_type == SettlementSourceType.PAYMENT)
            .filter(InvoiceSettlementAllocation.source_id == str(payment.id))
            .one_or_none()
            is not None
        )
        ledger_exists = (
            self.db.query(InternalLedgerTransaction.id)
            .filter(InternalLedgerTransaction.external_ref_type == "PAYMENT")
            .filter(InternalLedgerTransaction.external_ref_id == str(payment.id))
            .one_or_none()
            is not None
        )
        return allocation_exists and ledger_exists

    def _resolve_tenant_id(self, request_ctx: RequestContext | None) -> int:
        if request_ctx and request_ctx.tenant_id is not None:
            return int(request_ctx.tenant_id)
        return 0

    def _policy_resource_for_invoice(self, invoice: Invoice, *, tenant_id: int) -> ResourceContext:
        period_status = None
        if invoice.billing_period_id:
            period = (
                self.db.query(BillingPeriod)
                .filter(BillingPeriod.id == invoice.billing_period_id)
                .one_or_none()
            )
            if period and period.status:
                period_status = period.status.value
        return ResourceContext(
            resource_type="INVOICE",
            tenant_id=tenant_id,
            client_id=invoice.client_id,
            status=period_status,
        )

    def _enforce_policy(
        self,
        *,
        token: dict | None,
        action: Action,
        invoice: Invoice,
    ) -> None:
        actor = actor_from_token(token)
        resource = self._policy_resource_for_invoice(invoice, tenant_id=actor.tenant_id)
        decision = self.policy_engine.check(actor=actor, action=action, resource=resource)
        if not decision.allowed:
            audit_access_denied(
                self.db,
                actor=actor,
                action=action,
                resource=resource,
                decision=decision,
                token=token,
            )
            raise PolicyAccessDenied(decision)

    def _ensure_settlement_allocation(
        self,
        *,
        invoice: Invoice,
        source_type: SettlementSourceType,
        source_id: str,
        amount: int,
        currency: str,
        applied_at: datetime | None,
        request_ctx: RequestContext | None,
        override: bool = False,
    ) -> InvoiceSettlementAllocation:
        existing = (
            self.db.query(InvoiceSettlementAllocation)
            .filter(InvoiceSettlementAllocation.invoice_id == invoice.id)
            .filter(InvoiceSettlementAllocation.source_type == source_type)
            .filter(InvoiceSettlementAllocation.source_id == source_id)
            .one_or_none()
        )
        if existing:
            return existing

        event_at = applied_at or datetime.now(timezone.utc)
        settlement_period = resolve_settlement_period(self.db, event_at=event_at)
        self.invariant_checker.check_settlement_allocation(
            invoice=invoice,
            amount=amount,
            settlement_period_id=str(settlement_period.id),
            override=override,
            request_ctx=request_ctx,
            audit=False,
        )
        allocation = InvoiceSettlementAllocation(
            invoice_id=invoice.id,
            tenant_id=self._resolve_tenant_id(request_ctx),
            client_id=invoice.client_id,
            settlement_period_id=settlement_period.id,
            source_type=source_type,
            source_id=source_id,
            amount=amount,
            currency=currency,
            applied_at=event_at,
        )
        try:
            nested = self.db.begin_nested()
            self.db.add(allocation)
            self.db.flush()
            nested.commit()
        except IntegrityError:
            nested.rollback()
            existing = (
                self.db.query(InvoiceSettlementAllocation)
                .filter(InvoiceSettlementAllocation.invoice_id == invoice.id)
                .filter(InvoiceSettlementAllocation.source_type == source_type)
                .filter(InvoiceSettlementAllocation.source_id == source_id)
                .one_or_none()
            )
            if existing:
                return existing
            raise

        event_type = {
            SettlementSourceType.PAYMENT: "INVOICE_PAYMENT_ALLOCATED",
            SettlementSourceType.CREDIT_NOTE: "CREDIT_NOTE_ALLOCATED",
            SettlementSourceType.REFUND: "REFUND_ALLOCATED",
        }[source_type]
        AuditService(self.db).audit(
            event_type=event_type,
            entity_type="invoice",
            entity_id=invoice.id,
            action="SETTLEMENT_ALLOCATED",
            after={
                "invoice_id": invoice.id,
                "source_type": source_type.value,
                "source_id": source_id,
                "amount": amount,
                "currency": currency,
                "settlement_period_id": str(settlement_period.id),
                "charge_period_id": str(invoice.billing_period_id) if invoice.billing_period_id else None,
            },
            request_ctx=request_ctx,
        )

        source_obj = None
        if source_type == SettlementSourceType.PAYMENT:
            source_obj = (
                self.db.query(InvoicePayment)
                .filter(InvoicePayment.id == source_id)
                .one_or_none()
            )
        elif source_type == SettlementSourceType.CREDIT_NOTE:
            source_obj = (
                self.db.query(CreditNote)
                .filter(CreditNote.id == source_id)
                .one_or_none()
            )
        elif source_type == SettlementSourceType.REFUND:
            source_obj = (
                self.db.query(RefundRequest)
                .filter(RefundRequest.id == source_id)
                .one_or_none()
            )

        try:
            graph_context = GraphContext(tenant_id=allocation.tenant_id, request_ctx=request_ctx)
            LegalGraphBuilder(self.db, context=graph_context).ensure_settlement_allocation_graph(
                allocation,
                invoice=invoice,
                source=source_obj,
            )
        except Exception as exc:  # noqa: BLE001 - graph should not block settlement
            logger.warning(
                "legal_graph_settlement_allocation_failed",
                extra={"allocation_id": str(allocation.id), "error": str(exc)},
            )
            audit_graph_write_failure(
                self.db,
                failure=LegalGraphWriteFailure(
                    entity_type="settlement_allocation",
                    entity_id=str(allocation.id),
                    error=str(exc),
                ),
                request_ctx=request_ctx,
            )

        return allocation

    def _apply_financial_transition(
        self,
        invoice: Invoice,
        *,
        target: InvoiceStatus,
        payment_amount: int | None = None,
        credit_note_amount: int | None = None,
        refund_amount: int | None = None,
        request_ctx: RequestContext | None = None,
    ) -> None:
        machine = InvoiceStateMachine(invoice, db=self.db)
        machine.transition(
            to=target,
            actor="finance_service",
            reason="financial_update",
            payment_amount=payment_amount,
            credit_note_amount=credit_note_amount,
            refund_amount=refund_amount,
            metadata={"source": "finance"},
            request_ctx=request_ctx,
        )

    def apply_payment(
        self,
        *,
        invoice_id: str,
        amount: int,
        currency: str,
        idempotency_key: str,
        external_ref: str | None = None,
        provider: str | None = None,
        request_ctx: RequestContext | None = None,
        token: dict | None = None,
    ) -> PaymentResult:
        idempotency_key = self._normalize_idempotency_key(idempotency_key)
        replay_from_flow = self._replay_from_money_flow_event(
            invoice_id=invoice_id,
            idempotency_key=idempotency_key,
            amount=amount,
            currency=currency,
            external_ref=external_ref,
            provider=provider,
            request_ctx=request_ctx,
            token=token,
        )
        if replay_from_flow:
            return replay_from_flow
        try:
            existing = self._resolve_existing_payment(
                invoice_id=invoice_id,
                idempotency_key=idempotency_key,
                external_ref=external_ref,
                provider=provider,
            )
            if existing:
                self._validate_payment_replay(
                    payment=existing,
                    amount=amount,
                    currency=currency,
                    external_ref=external_ref,
                    provider=provider,
                )
                return self._replay_payment(
                    invoice_id=invoice_id,
                    payment=existing,
                    request_ctx=request_ctx,
                    token=token,
                )
        except InvoiceNotFound:
            billing_metrics.mark_payment_error()
            billing_metrics.mark_payment_failed()
            raise

        txn_context = nullcontext() if self.db.in_transaction() else self.db.begin()
        job_run = None

        with txn_context:
            lock_token = make_lock_token("finance_payment", idempotency_key)
            with advisory_lock(self.db, lock_token) as acquired:
                if not acquired:
                    billing_metrics.mark_payment_failed()
                    raise FinanceOperationInProgress(idempotency_key)

            try:
                self.db.execute(text("SELECT 1"))
            except DBAPIError:
                self.db.rollback()
                raise

            invoice = self._lock_invoice(invoice_id)
            self._enforce_policy(token=token, action=Action.PAYMENT_APPLY, invoice=invoice)
            existing = self._resolve_existing_payment(
                invoice_id=invoice_id,
                idempotency_key=idempotency_key,
                external_ref=external_ref,
                provider=provider,
            )
            if existing:
                self._validate_payment_replay(
                    payment=existing,
                    amount=amount,
                    currency=currency,
                    external_ref=external_ref,
                    provider=provider,
                )
                return self._replay_payment(
                    invoice_id=invoice_id,
                    payment=existing,
                    request_ctx=request_ctx,
                    token=token,
                    invoice=invoice,
                )
            try:
                self.invariant_checker.check_invoice(invoice, request_ctx=request_ctx, audit=False)
                self.invariant_checker.check_payment_application(
                    invoice,
                    amount=amount,
                    idempotency_key=idempotency_key,
                    request_ctx=request_ctx,
                    audit=False,
                )
            except FinancialInvariantViolation as exc:
                self.db.rollback()
                billing_metrics.mark_payment_error()
                billing_metrics.mark_payment_failed()
                self._audit_invariant_violation(
                    exc,
                    request_ctx=request_ctx,
                    extra_payload={"invoice_id": invoice.id},
                )
                raise
            self._require_settlement_period(invoice, action="payment")
            job_run = self.job_service.start(
                BillingJobType.FINANCE_PAYMENT,
                params={
                    "invoice_id": invoice_id,
                    "amount": amount,
                    "currency": currency,
                    "external_ref": external_ref,
                    "provider": provider,
                },
                correlation_id=idempotency_key,
                invoice_id=invoice_id,
            )
            payment = InvoicePayment(
                invoice_id=invoice_id,
                amount=amount,
                currency=currency,
                idempotency_key=idempotency_key,
                external_ref=external_ref,
                provider=provider,
                status=PaymentStatus.POSTED,
            )
            try:
                nested = self.db.begin_nested()
                self.db.add(payment)
                self.db.flush()
                nested.commit()
            except IntegrityError:
                nested.rollback()
                existing = self._resolve_existing_payment(
                    invoice_id=invoice_id,
                    idempotency_key=idempotency_key,
                    external_ref=external_ref,
                    provider=provider,
                )
                if existing:
                    self._validate_payment_replay(
                        payment=existing,
                        amount=amount,
                        currency=currency,
                        external_ref=external_ref,
                        provider=provider,
                    )
                    return self._replay_payment(
                        invoice_id=invoice_id,
                        payment=existing,
                        request_ctx=request_ctx,
                        token=token,
                        invoice=invoice,
                    )
                raise
            InternalLedgerService(self.db).post_payment_applied(
                invoice=invoice,
                payment=payment,
                tenant_id=self._resolve_tenant_id(request_ctx),
            )
            ledger_tx = (
                self.db.query(InternalLedgerTransaction)
                .filter(InternalLedgerTransaction.external_ref_type == "PAYMENT")
                .filter(InternalLedgerTransaction.external_ref_id == str(payment.id))
                .one_or_none()
            )
            event, event_created = self._ensure_payment_money_flow_event(
                invoice=invoice,
                payment=payment,
                tenant_id=self._resolve_tenant_id(request_ctx),
                ledger_transaction_id=str(ledger_tx.id) if ledger_tx else None,
                idempotency_key=idempotency_key,
            )

            if event_created:
                current_paid = int(invoice.amount_paid or 0)
                current_credits = int(getattr(invoice, "credited_amount", 0) or 0)
                current_refunded = int(getattr(invoice, "amount_refunded", 0) or 0)
                total = int(invoice.total_with_tax or invoice.total_amount or 0)
                outstanding_before = total - current_paid - current_credits + current_refunded

                if invoice.status not in {InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE}:
                    self.db.rollback()
                    billing_metrics.mark_payment_error()
                    raise InvalidTransitionError(
                        f"payments allowed only from sent/partial/overdue, got {invoice.status}"
                    )

                try:
                    target_status = InvoiceStatus.PARTIALLY_PAID
                    if amount >= outstanding_before:
                        target_status = InvoiceStatus.PAID

                    self._apply_financial_transition(
                        invoice,
                        target=target_status,
                        payment_amount=amount,
                        request_ctx=request_ctx,
                    )
                    self.invariant_checker.check_invoice(invoice, request_ctx=request_ctx, audit=False)
                except (InvalidTransitionError, InvoiceInvariantError):
                    self.db.rollback()
                    billing_metrics.mark_payment_error()
                    billing_metrics.mark_payment_failed()
                    raise
                except FinancialInvariantViolation as exc:
                    self.db.rollback()
                    billing_metrics.mark_payment_error()
                    billing_metrics.mark_payment_failed()
                    self._audit_invariant_violation(
                        exc,
                        request_ctx=request_ctx,
                        extra_payload={"invoice_id": invoice.id},
                    )
                    raise

                self._ensure_settlement_allocation(
                    invoice=invoice,
                    source_type=SettlementSourceType.PAYMENT,
                    source_id=str(payment.id),
                    amount=amount,
                    currency=currency,
                    applied_at=payment.created_at,
                    request_ctx=request_ctx,
                )

            self.job_service.succeed(
                job_run,
                metrics={
                    "invoice_id": invoice_id,
                    "amount": amount,
                    "currency": currency,
                    "due_amount": invoice.amount_due,
                },
                result_ref={
                    "invoice_id": invoice_id,
                    "payment_id": str(payment.id),
                    "due_amount": invoice.amount_due,
                },
            )
            if event_created:
                billing_metrics.mark_payment_posted()
                billing_metrics.mark_payment_amount(amount)
                if invoice.status == InvoiceStatus.PAID:
                    billing_metrics.mark_invoice_paid()
            return PaymentResult(payment=payment, invoice=invoice, is_replay=not event_created)

    def create_credit_note(
        self,
        *,
        invoice_id: str,
        amount: int,
        currency: str,
        reason: str | None,
        idempotency_key: str,
        request_ctx: RequestContext | None = None,
        token: dict | None = None,
    ) -> CreditNoteResult:
        idempotency_key = self._normalize_idempotency_key(idempotency_key)
        existing = (
            self.db.query(CreditNote)
            .filter(CreditNote.idempotency_key == idempotency_key)
            .one_or_none()
        )
        if existing:
            invoice = self._lock_invoice(invoice_id)
            self._enforce_policy(token=token, action=Action.CREDIT_NOTE_CREATE, invoice=invoice)
            InternalLedgerService(self.db).post_credit_note_applied(
                invoice=invoice,
                credit_note=existing,
                tenant_id=self._resolve_tenant_id(request_ctx),
            )
            self._ensure_settlement_allocation(
                invoice=invoice,
                source_type=SettlementSourceType.CREDIT_NOTE,
                source_id=str(existing.id),
                amount=int(existing.amount),
                currency=existing.currency,
                applied_at=existing.created_at,
                request_ctx=request_ctx,
            )
            return CreditNoteResult(credit_note=existing, invoice=invoice, is_replay=True)

        txn_context = nullcontext() if self.db.in_transaction() else self.db.begin()
        job_run = None

        with txn_context:
            lock_token = make_lock_token("finance_credit_note", idempotency_key)
            with advisory_lock(self.db, lock_token) as acquired:
                if not acquired:
                    raise FinanceOperationInProgress(idempotency_key)

            invoice = self._lock_invoice(invoice_id)
            try:
                self.invariant_checker.check_invoice(invoice, request_ctx=request_ctx, audit=False)
            except FinancialInvariantViolation as exc:
                self.db.rollback()
                self._audit_invariant_violation(
                    exc,
                    request_ctx=request_ctx,
                    extra_payload={"invoice_id": invoice.id},
                )
                raise
            tenant_id = self._resolve_tenant_id(request_ctx)
            decision_context = DecisionContext(
                tenant_id=tenant_id,
                client_id=invoice.client_id,
                actor_type="ADMIN",
                action=DecisionAction.CREDIT_NOTE_CREATE,
                amount=amount,
                currency=currency,
                invoice_id=invoice.id,
                billing_period_id=str(invoice.billing_period_id) if invoice.billing_period_id else None,
                history={},
                metadata={
                    "invoice_status": invoice.status.value if invoice.status else None,
                    "billing_period_status": self._policy_resource_for_invoice(invoice, tenant_id=tenant_id).status,
                    "actor_roles": token.get("roles") if token else [],
                    "subject_id": invoice.id,
                },
            )
            decision = DecisionEngine(self.db).evaluate(decision_context)
            if decision.outcome != DecisionOutcome.ALLOW:
                raise InvalidTransitionError(f"DECISION_{decision.outcome.value}")
            self._enforce_policy(token=token, action=Action.CREDIT_NOTE_CREATE, invoice=invoice)
            self._require_settlement_period(invoice, action="credit_note")
            job_run = self.job_service.start(
                BillingJobType.FINANCE_CREDIT_NOTE,
                params={"invoice_id": invoice_id, "amount": amount, "currency": currency, "reason": reason},
                correlation_id=idempotency_key,
                invoice_id=invoice_id,
            )

            credit_note = CreditNote(
                invoice_id=invoice_id,
                amount=amount,
                currency=currency,
                reason=reason,
                idempotency_key=idempotency_key,
                status=CreditNoteStatus.POSTED,
            )
            self.db.add(credit_note)
            try:
                current_credits = int(getattr(invoice, "credited_amount", 0) or 0)
                current_refunded = int(getattr(invoice, "amount_refunded", 0) or 0)
                current_paid = int(invoice.amount_paid or 0)
                total = int(invoice.total_with_tax or invoice.total_amount or 0)
                remaining_after_credit = total - current_paid - (current_credits + amount) + current_refunded
                if invoice.status not in {InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID}:
                    self.db.rollback()
                    raise InvalidTransitionError(f"credit notes allowed only from sent/partial, got {invoice.status}")

                if invoice.status == InvoiceStatus.SENT:
                    self._apply_financial_transition(
                        invoice,
                        target=InvoiceStatus.PARTIALLY_PAID,
                        credit_note_amount=amount,
                        request_ctx=request_ctx,
                    )
                    if invoice.amount_due <= 0:
                        self._apply_financial_transition(
                            invoice,
                            target=InvoiceStatus.PAID,
                            request_ctx=request_ctx,
                        )
                else:
                    target_status = InvoiceStatus.PARTIALLY_PAID
                    if remaining_after_credit <= 0:
                        target_status = InvoiceStatus.PAID

                    self._apply_financial_transition(
                        invoice,
                        target=target_status,
                        credit_note_amount=amount,
                        request_ctx=request_ctx,
                    )
                self.invariant_checker.check_invoice(invoice, request_ctx=request_ctx, audit=False)
            except (InvalidTransitionError, InvoiceInvariantError):
                self.db.rollback()
                raise
            except FinancialInvariantViolation as exc:
                self.db.rollback()
                self._audit_invariant_violation(
                    exc,
                    request_ctx=request_ctx,
                    extra_payload={"invoice_id": invoice.id},
                )
                raise

            self._ensure_settlement_allocation(
                invoice=invoice,
                source_type=SettlementSourceType.CREDIT_NOTE,
                source_id=str(credit_note.id),
                amount=amount,
                currency=currency,
                applied_at=credit_note.created_at,
                request_ctx=request_ctx,
            )
            InternalLedgerService(self.db).post_credit_note_applied(
                invoice=invoice,
                credit_note=credit_note,
                tenant_id=self._resolve_tenant_id(request_ctx),
            )

            self.job_service.succeed(
                job_run,
                metrics={
                    "invoice_id": invoice_id,
                    "amount": amount,
                    "currency": currency,
                    "due_amount": invoice.amount_due,
                },
                result_ref={
                    "invoice_id": invoice_id,
                    "credit_note_id": str(credit_note.id),
                    "due_amount": invoice.amount_due,
                },
            )
            return CreditNoteResult(credit_note=credit_note, invoice=invoice, is_replay=False)

    def create_refund(
        self,
        *,
        invoice_id: str,
        amount: int,
        currency: str,
        reason: str | None,
        external_ref: str | None,
        provider: str | None,
        request_ctx: RequestContext | None = None,
        token: dict | None = None,
    ) -> CreditNoteResult:
        if external_ref:
            existing_by_ref = (
                self.db.query(CreditNote)
                .filter(CreditNote.external_ref == external_ref)
                .filter(CreditNote.provider == provider)
                .one_or_none()
            )
            if existing_by_ref:
                if existing_by_ref.invoice_id != invoice_id:
                    raise RefundReferenceConflict(external_ref)
                invoice = self._lock_invoice(invoice_id)
                self._enforce_policy(token=token, action=Action.CREDIT_NOTE_CREATE, invoice=invoice)
                InternalLedgerService(self.db).post_refund_applied(
                    invoice=invoice,
                    refund=existing_by_ref,
                    tenant_id=self._resolve_tenant_id(request_ctx),
                )
                self._ensure_settlement_allocation(
                    invoice=invoice,
                    source_type=SettlementSourceType.REFUND,
                    source_id=str(existing_by_ref.id),
                    amount=int(existing_by_ref.amount),
                    currency=existing_by_ref.currency,
                    applied_at=existing_by_ref.created_at,
                    request_ctx=request_ctx,
                )
                return CreditNoteResult(credit_note=existing_by_ref, invoice=invoice, is_replay=True)

        txn_context = nullcontext() if self.db.in_transaction() else self.db.begin()
        job_run = None

        with txn_context:
            lock_token = make_lock_token("finance_refund", external_ref or f"{invoice_id}:{amount}")
            with advisory_lock(self.db, lock_token) as acquired:
                if not acquired:
                    billing_metrics.mark_payment_error()

            invoice = self._lock_invoice(invoice_id)
            self._enforce_policy(token=token, action=Action.CREDIT_NOTE_CREATE, invoice=invoice)
            try:
                self.invariant_checker.check_invoice(invoice, request_ctx=request_ctx, audit=False)
                self.invariant_checker.check_refund(
                    invoice,
                    amount=amount,
                    reference=external_ref or f"refund:{invoice_id}",
                    request_ctx=request_ctx,
                    audit=False,
                )
            except FinancialInvariantViolation as exc:
                self.db.rollback()
                self._audit_invariant_violation(
                    exc,
                    request_ctx=request_ctx,
                    extra_payload={"invoice_id": invoice.id},
                )
                raise
            self._require_settlement_period(invoice, action="refund")
            if invoice.status not in {InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID}:
                self.db.rollback()
                raise InvalidTransitionError(
                    f"refunds allowed only from paid/partial, got {invoice.status}"
                )

            job_run = self.job_service.start(
                BillingJobType.FINANCE_CREDIT_NOTE,
                params={
                    "invoice_id": invoice_id,
                    "amount": amount,
                    "currency": currency,
                    "reason": reason,
                    "external_ref": external_ref,
                    "provider": provider,
                },
                correlation_id=external_ref or f"refund:{invoice_id}",
                invoice_id=invoice_id,
            )

            refund = CreditNote(
                invoice_id=invoice_id,
                amount=amount,
                currency=currency,
                reason=reason,
                idempotency_key=external_ref or f"refund:{invoice_id}:{amount}",
                external_ref=external_ref,
                provider=provider,
                status=CreditNoteStatus.POSTED,
            )
            self.db.add(refund)

            try:
                current_paid = int(invoice.amount_paid or 0)
                current_refunded = int(getattr(invoice, "amount_refunded", 0) or 0)
                net_paid_after = current_paid - (current_refunded + amount)
                target_status = InvoiceStatus.PARTIALLY_PAID
                if net_paid_after <= 0:
                    target_status = InvoiceStatus.SENT

                self._apply_financial_transition(
                    invoice,
                    target=target_status,
                    refund_amount=amount,
                    request_ctx=request_ctx,
                )
                self.db.flush()
                self.invariant_checker.check_invoice(invoice, request_ctx=request_ctx, audit=False)
            except IntegrityError:
                self.db.rollback()
                if external_ref:
                    existing = (
                        self.db.query(CreditNote)
                        .filter(CreditNote.external_ref == external_ref)
                        .filter(CreditNote.provider == provider)
                        .one_or_none()
                    )
                    if existing:
                        invoice = self._lock_invoice(invoice_id)
                        InternalLedgerService(self.db).post_refund_applied(
                            invoice=invoice,
                            refund=existing,
                            tenant_id=self._resolve_tenant_id(request_ctx),
                        )
                        self._ensure_settlement_allocation(
                            invoice=invoice,
                            source_type=SettlementSourceType.REFUND,
                            source_id=str(existing.id),
                            amount=int(existing.amount),
                            currency=existing.currency,
                            applied_at=existing.created_at,
                            request_ctx=request_ctx,
                        )
                        return CreditNoteResult(credit_note=existing, invoice=invoice, is_replay=True)
                raise
            except (InvalidTransitionError, InvoiceInvariantError):
                self.db.rollback()
                raise
            except FinancialInvariantViolation as exc:
                self.db.rollback()
                self._audit_invariant_violation(
                    exc,
                    request_ctx=request_ctx,
                    extra_payload={"invoice_id": invoice.id},
                )
                raise

            self._ensure_settlement_allocation(
                invoice=invoice,
                source_type=SettlementSourceType.REFUND,
                source_id=str(refund.id),
                amount=amount,
                currency=currency,
                applied_at=refund.created_at,
                request_ctx=request_ctx,
            )
            InternalLedgerService(self.db).post_refund_applied(
                invoice=invoice,
                refund=refund,
                tenant_id=self._resolve_tenant_id(request_ctx),
            )

            self.job_service.succeed(
                job_run,
                metrics={
                    "invoice_id": invoice_id,
                    "amount": amount,
                    "currency": currency,
                    "due_amount": invoice.amount_due,
                },
                result_ref={
                    "invoice_id": invoice_id,
                    "credit_note_id": str(refund.id),
                    "due_amount": invoice.amount_due,
                },
            )
            billing_metrics.mark_refund_posted()
            return CreditNoteResult(credit_note=refund, invoice=invoice, is_replay=False)
